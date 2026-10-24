"""Añade observación a adaptadores de Manifiestos; conserva todas sus consultas."""
from functools import wraps
from .activity import observed,stage,CURRENT


def manifest_subject(self,*args,**kwargs):
    for value in reversed(args):
        if isinstance(value,dict) and 'Manifiesto' in value:
            return '-'.join(str(value.get(k,'')).strip() for k in ('Trans.','Ing Sal','Manifiesto','Cod Ubicacion','Fecha'))
    if args and isinstance(args[0],str) and args[0] in ('maritimo','aereo','terrestre'):
        return ' · '.join(map(str,args[:3]))
    return ''


def install(scraper):
    import conocimientos
    import tablas_flow
    conocimientos.parse_page=observed('Interpretando y validando página de Conocimientos')(conocimientos.parse_page)
    tablas_flow.parse_table=observed('Interpretando y validando página de manifiesto')(tablas_flow.parse_table)
    original=conocimientos.request_html
    if not getattr(original,'_workbench_observed',False):
        @wraps(original)
        async def request_html(request,url,timeout,form=None,**kwargs):
            if CURRENT.get() is None:return await original(request,url,timeout,form,**kwargs)
            callback=kwargs.get('activity_callback')
            limit=f'límite {timeout} s' if timeout else 'sin límite de tiempo; Detener disponible'
            with stage('Esperando respuesta HTTP · '+limit) as update:
                def activity(event):
                    kind=event['stage']
                    if kind=='response':update(f"HTTP {event['status']} recibido · leyendo contenido")
                    elif kind=='request':update(f"Esperando HTTP · intento {event['attempt']}/{event['max_attempts']} · {limit}")
                    elif kind in ('retry','error'):update(('Reintentando HTTP' if kind=='retry' else 'Error HTTP')+' · '+event.get('error',''))
                    if callback:callback(event)
                kwargs['activity_callback']=activity
                return await original(request,url,timeout,form,**kwargs)
        request_html._workbench_observed=True
        conocimientos.request_html=request_html
    methods={'open_page':'Abriendo página principal de TICA','_query_conoc_main':'Consultando listado de manifiestos',
        '_fetch_conoc_result':'Extrayendo Conocimientos del manifiesto','_fetch_tracked_result':'Extrayendo tabla del manifiesto',
        '_renew_conoc_link':'Renovando formulario y enlace de consulta','write_conoc_failures':'Exportando CSV mensual y pendientes',
        '_open_sub_page':'Abriendo detalle en TICA','container_result':'Extrayendo contenedores y mercancías',
        'run_main_job':'Descargando listado mensual de manifiestos',
        'run_conocimientos_for_mode':'Consultando Conocimientos',
        'run_tracked_table':'Consultando tablas de manifiestos',
        'run_container_jobs':'Consultando contenedores'}
    for name,label in methods.items():
        setattr(scraper,name,observed(label,manifest_subject)(getattr(scraper,name)))

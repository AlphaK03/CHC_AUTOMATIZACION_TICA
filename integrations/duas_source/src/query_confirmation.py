"""Confirma respuestas de Confirmar; el cero inicial del formulario no es evidencia."""
import json
import re


INSTALL_OBSERVER = r'''
const expected = arguments[0];
const state = window.chcQueryConfirmation = {requests: []};
const originalOpen = XMLHttpRequest.prototype.open;
const originalSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.chcQueryMethod = String(method).toUpperCase();
    this.chcQueryURL = new URL(url, location.href);
    return originalOpen.call(this, method, url, ...rest);
};
XMLHttpRequest.prototype.send = function(body) {
    const fields = new URLSearchParams(typeof body === 'string' ? body : '');
    const event = fields.get('GXState') || '';
    const url = this.chcQueryURL;
    if (this.chcQueryMethod === 'POST' && url &&
        url.origin === location.origin && url.pathname === location.pathname &&
        /"_EventName"\s*:\s*"EENTER\."/.test(event)) {
        const reply = {done: false, requested: {
            start: fields.get('vVFCHINI'), end: fields.get('vVFCHFIN'),
            regimenCode: fields.get('vCODI_REGI')
        }};
        // Asociar la respuesta al envío exacto, incluido el CAPTCHA introducido.
        if (reply.requested.start !== expected.start ||
            reply.requested.end !== expected.end ||
            reply.requested.regimenCode !== expected.regimenCode ||
            fields.get('cfield') !== expected.captcha) {
            reply.error = 'El envío no coincide con la consulta solicitada.';
        }
        state.requests.push(reply);
        this.addEventListener('loadend', () => {
            reply.status = this.status;
            try {
                const finalURL = new URL(this.responseURL);
                if (finalURL.origin !== url.origin || finalURL.pathname !== url.pathname)
                    reply.error = 'TICA redirigió la consulta a otra página.';
                reply.text = this.responseText;
            } catch (_) { reply.error = 'No se pudo leer la respuesta de TICA.'; }
            reply.done = true;
        });
    }
    return originalSend.call(this, body);
};
'''


def confirmed_count(reply, expected):
    """Cantidad confirmada por el servidor o ValueError; nunca presume un vacío."""
    if (not reply.get('done') or reply.get('error') or reply.get('status') != 200):
        raise ValueError('TICA no confirmó la consulta: error de envío o conexión.')
    keys = ('start', 'end', 'regimenCode')
    if reply.get('requested') != {key: expected[key] for key in keys}:
        raise ValueError('La respuesta pertenece a otra consulta.')
    try:
        response = json.loads(reply['text'])
        if not isinstance(response, dict):
            raise ValueError('La respuesta de TICA no es un resultado reconocible.')
        messages = response['gxMessages']
        if (not isinstance(messages, dict) or messages.get('MAIN') != [] or
                any(not isinstance(items, list) or items for items in messages.values())):
            raise ValueError('TICA devolvió mensajes; la consulta queda pendiente.')
        hidden = response['gxHiddens']
        if hidden.get('CAPTCHA1_Validationresult') != '1':
            raise ValueError('TICA no aceptó el CAPTCHA; la consulta queda pendiente.')
        values = [item for item in response['gxValues']
                  if item.get('CmpContext') == '' and item.get('IsMasterPage') == 'False']
        props = [item for item in response['gxProps']
                 if item.get('CmpContext') == '' and item.get('IsMasterPage') == 'False']
        grids = [item for item in response['gxGrids']
                 if item.get('GridName') == 'Subfile1' and item.get('CmpContext') == '']
        if len(values) != 1 or len(props) != 1 or len(grids) != 1:
            raise ValueError('La respuesta no identifica un resultado único.')
        values, props, grid = values[0], props[0], grids[0]
        for field, key in [('AV35vFchIni', 'start'), ('AV32vFchFin', 'end'),
                           ('AV13CODI_REGI', 'regimenCode')]:
            if values.get(field) != expected[key]:
                raise ValueError('TICA confirmó otras fechas o régimen.')
        for field in ('AV24TIPO_OPERA', 'AV31vEstado', 'AV27vCodAdu',
                      'AV12CODI_ALMA', 'AV28vCodAdu2', 'AV8CALMDEST'):
            if values.get(field) != '':
                raise ValueError('TICA devolvió filtros distintos de los solicitados.')
        def number(value):
            if not re.fullmatch(r'[0-9]+', str(value)):
                raise ValueError('TICA no confirmó una cantidad válida.')
            return int(value)
        count = number(hidden['vVCANTREG'])
        grid_count = number(grid['Count'])
        if (count != number(values['AV26vCantReg']) or
                grid_count != number(hidden['nRC_Subfile1']) or
                grid_count > count or (count > 0 and grid_count == 0)):
            raise ValueError('Las cantidades del resultado no coinciden.')
        if count == 0:
            if (json.loads(hidden['Subfile1ContainerDataV']) != [] or
                    props['BUTTON6'].get('Visible') != '0' or
                    props['MENS'].get('Visible') != '0'):
                raise ValueError('TICA no confirmó un resultado vacío coherente.')
        return count
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError) as error:
        raise ValueError('La respuesta de TICA está incompleta o no es reconocible.') from error

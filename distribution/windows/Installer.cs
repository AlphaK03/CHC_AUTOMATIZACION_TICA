using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("Instalador CHC Workbench")]
[assembly: AssemblyProduct("CHC Workbench")]
[assembly: AssemblyCompany("CHC Consultores")]
[assembly: AssemblyVersion("2026.10.22.0")]

internal static class Installer {
    private static string Extract(string target, Action<int> progress) {
        target = Path.GetFullPath(target);
        if (Directory.Exists(target)) throw new IOException("La carpeta de destino ya existe. Elige una carpeta nueva.");
        Directory.CreateDirectory(target);
        string prefix = target.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using (var zip = new ZipArchive(stream, ZipArchiveMode.Read)) {
            int count = 0;
            foreach (ZipArchiveEntry entry in zip.Entries) {
                string file = Path.GetFullPath(Path.Combine(target, entry.FullName));
                if (!file.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) throw new IOException("Ruta de paquete no valida.");
                Directory.CreateDirectory(Path.GetDirectoryName(file));
                using (Stream source = entry.Open())
                using (Stream output = new FileStream(file, FileMode.CreateNew, FileAccess.Write)) source.CopyTo(output);
                progress(++count * 100 / zip.Entries.Count);
            }
        }
        string exe = Path.Combine(target, "CHC Workbench.exe");
        if (!File.Exists(exe)) throw new IOException("El paquete esta incompleto.");
        return exe;
    }

    private static void Shortcut(string folder, string exe) {
        Directory.CreateDirectory(folder);
        Type type = Type.GetTypeFromProgID("WScript.Shell");
        object shell = Activator.CreateInstance(type);
        object link = type.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell,
            new object[] { Path.Combine(folder, "CHC Workbench.lnk") });
        Type linkType = link.GetType();
        linkType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { exe });
        linkType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { Path.GetDirectoryName(exe) });
        linkType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { exe + ",0" });
        linkType.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
    }

    [STAThread]
    private static int Main(string[] args) {
        AppContext.SetSwitch("Switch.System.IO.UseLegacyPathHandling", false);
        AppContext.SetSwitch("Switch.System.IO.BlockLongPaths", false);
        if (args.Length == 2 && args[0] == "--extract-only") {
            try { Extract(args[1], p => {}); return 0; }
            catch { return 1; }
        }
        Application.EnableVisualStyles();
        var form = new Form { Text = "Instalar CHC Workbench", Width = 510, Height = 225,
            StartPosition = FormStartPosition.CenterScreen, FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false };
        form.Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        var label = new Label { Left = 24, Top = 22, Width = 450, Height = 60,
            Text = "CHC Workbench para Windows de 64 bits\nIncluye Python, navegador y todos los bots.\nTus bases y resultados se guardan separados del programa." };
        var bar = new ProgressBar { Left = 24, Top = 94, Width = 446, Height = 18 };
        var button = new Button { Text = "Instalar y abrir", Left = 300, Top = 130, Width = 170, Height = 32 };
        form.Controls.AddRange(new Control[] { label, bar, button });
        var worker = new BackgroundWorker { WorkerReportsProgress = true };
        bool attempted = false;
        string target = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs", "CHC Workbench", DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 6));
        worker.DoWork += (sender, e) => e.Result = Extract(target, p => worker.ReportProgress(p));
        worker.ProgressChanged += (sender, e) => bar.Value = e.ProgressPercentage;
        worker.RunWorkerCompleted += (sender, e) => {
            if (e.Error != null) {
                label.Text = "No se pudo completar la instalacion.\n" + e.Error.Message;
                button.Text = "Cerrar"; button.Enabled = true; button.Click += (s, ev) => form.Close(); return;
            }
            string exe = (string)e.Result;
            try {
                Shortcut(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), exe);
                Shortcut(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "CHC Consultores"), exe);
            } catch {
                MessageBox.Show("La app esta instalada. Puedes abrirla desde:\n" + exe, "CHC Workbench");
            }
            Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true });
            form.Close();
        };
        button.Click += (sender, e) => { if (!attempted) { attempted = true; button.Enabled = false; label.Text = "Instalando CHC Workbench...\nNo cierres esta ventana."; worker.RunWorkerAsync(); } };
        form.FormClosing += (sender, e) => { if (worker.IsBusy) e.Cancel = true; };
        Application.Run(form);
        return 0;
    }
}

using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("CHC Workbench")]
[assembly: System.Reflection.AssemblyProduct("CHC Workbench")]
[assembly: System.Reflection.AssemblyCompany("CHC Consultores")]
[assembly: System.Reflection.AssemblyVersion("2026.10.22.0")]

internal static class Launcher {
    // Windows CommandLineToArgvW quoting, including trailing slashes and quotes.
    internal static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') result.Append('\\', slashes * 2 + 1);
            else result.Append('\\', slashes);
            result.Append(c); slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }

    [STAThread]
    private static int Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, "workbench", ".venv", "Scripts", "pythonw.exe");
            if (!File.Exists(python) || !File.Exists(Path.Combine(root, "distribution.json")))
                throw new IOException("Extrae toda la carpeta de CHC Workbench antes de abrir la aplicacion.");
            string home = Environment.GetEnvironmentVariable("CHC_WORKBENCH_HOME");
            if (String.IsNullOrWhiteSpace(home)) home = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CHC Consultores", "Workbench");
            string logs = Path.Combine(home, "runtime", "workbench", "logs");
            Directory.CreateDirectory(logs);
            var command = new StringBuilder("-X utf8 " + Quote(Path.Combine(root, "workbench", "app.py")));
            foreach (string arg in args) command.Append(" ").Append(Quote(arg));
            var start = new ProcessStartInfo(python, command.ToString()) {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            foreach (string key in new [] { "PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH" })
                start.EnvironmentVariables.Remove(key);
            start.EnvironmentVariables["CHC_WORKBENCH_HOME"] = home;
            start.EnvironmentVariables["PLAYWRIGHT_BROWSERS_PATH"] = Path.Combine(root, "_runtime", "browsers");
            start.EnvironmentVariables["PYTHONUTF8"] = "1";
            start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            string log = Path.Combine(logs, "inicio-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Process.GetCurrentProcess().Id + ".log");
            using (var writer = new StreamWriter(log, false, new UTF8Encoding(false))) {
                object gate = new object();
                using (var process = new Process { StartInfo = start }) {
                    DataReceivedEventHandler receive = (sender, e) => { if (e.Data != null) lock(gate) { writer.WriteLine(e.Data); writer.Flush(); } };
                    process.OutputDataReceived += receive; process.ErrorDataReceived += receive;
                    process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine();
                    process.WaitForExit();
                    if (process.ExitCode != 0 && args.Length == 0)
                        MessageBox.Show("No se pudo iniciar CHC Workbench. Detalle en:\n" + log, "CHC Workbench", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return process.ExitCode;
                }
            }
        } catch (Exception error) {
            MessageBox.Show(error.Message, "CHC Workbench", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}

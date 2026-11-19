// TWIN launcher: a tiny windowed (no console) program that starts tools\launch.ps1 without any flashing window.
// Built on this computer by tools\launch.ps1 with the C# compiler that ships with Windows (.NET Framework 4):
//   csc /target:winexe /win32icon:tools\web\logo.ico /out:TWIN.exe tools\launcher\TWIN.cs
// Keep this file ASCII-only.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

static class Program
{
    [STAThread]
    static int Main(string[] args)
    {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        string ps1 = Path.Combine(dir, "tools", "launch.ps1");
        if (!File.Exists(ps1))
        {
            MessageBox.Show("tools/launch.ps1 was not found next to TWIN.exe.", "TWIN", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return 1;
        }
        var cmd = new StringBuilder("-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File \"" + ps1 + "\"");
        foreach (string a in args) cmd.Append(" \"").Append(a.Replace("\"", "")).Append('"');
        var psi = new ProcessStartInfo("powershell.exe", cmd.ToString());
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;  // no console window at all
        psi.WorkingDirectory = dir;
        Process.Start(psi);
        return 0;
    }
}

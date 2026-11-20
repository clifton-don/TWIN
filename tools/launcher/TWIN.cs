// TWIN launcher: a tiny windowed (no console) program that starts tools\launch.ps1 without any flashing window.
// Built on this computer by Open_Web.bat / tools\launch.ps1 with the C# compiler that ships with Windows (.NET Framework 4):
//   csc /target:winexe /win32icon:tools\web\logo.ico /out:TWIN.exe tools\launcher\TWIN.cs
// Two ways to run:
//   TWIN.exe [args]                         next to the TWIN folder's tools\ (normal double-click)
//   TWIN-autostart.exe --find <dir> [--prefer X:] [args]
//                                           start-on-login copy kept in %LOCALAPPDATA%\TWIN. The drive letter of a
//                                           removable disk can change, so it looks for <drive>:\<dir>\tools\launch.ps1
//                                           on every ready drive (preferred drive first). Not plugged in: exit quietly.
// Keep this file ASCII-only.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

static class Program
{
    static string FindTwin(string dir, string prefer)
    {
        var roots = new List<string>();
        if (!string.IsNullOrEmpty(prefer)) roots.Add(prefer.TrimEnd('\\') + "\\");
        foreach (DriveInfo d in DriveInfo.GetDrives())
        {
            try { if (d.IsReady && d.DriveType != DriveType.Network && !roots.Contains(d.RootDirectory.FullName)) roots.Add(d.RootDirectory.FullName); }
            catch (IOException) { }
        }
        foreach (string r in roots)
        {
            string ps1 = Path.Combine(r, dir, "tools", "launch.ps1");
            if (File.Exists(ps1)) return ps1;
        }
        return null;
    }

    [STAThread]
    static int Main(string[] args)
    {
        var rest = new List<string>(args);
        string ps1;
        if (rest.Count >= 2 && rest[0] == "--find")
        {
            string dir = rest[1], prefer = null;
            rest.RemoveRange(0, 2);
            if (rest.Count >= 2 && rest[0] == "--prefer") { prefer = rest[1]; rest.RemoveRange(0, 2); }
            ps1 = FindTwin(dir, prefer);
            if (ps1 == null) return 0;  // disk not plugged in: start nothing, say nothing
        }
        else
        {
            ps1 = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "tools", "launch.ps1");
            if (!File.Exists(ps1))
            {
                MessageBox.Show("tools/launch.ps1 was not found next to TWIN.exe.", "TWIN", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return 1;
            }
        }
        var cmd = new StringBuilder("-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File \"" + ps1 + "\"");
        foreach (string a in rest) cmd.Append(" \"").Append(a.Replace("\"", "")).Append('"');
        var psi = new ProcessStartInfo("powershell.exe", cmd.ToString());
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;  // no console window at all
        psi.WorkingDirectory = Path.GetDirectoryName(Path.GetDirectoryName(ps1));
        Process.Start(psi);
        return 0;
    }
}

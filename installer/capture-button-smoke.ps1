param([long]$Window, [string]$OutputFile)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FrankessoSmokeSnapshot {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hWnd, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
}
"@
$handle = [FrankessoSmokeSnapshot]::GetAncestor([IntPtr]$Window, 2)
$rect = [FrankessoSmokeSnapshot+Rect]::new()
if (-not [FrankessoSmokeSnapshot]::GetWindowRect($handle, [ref]$rect)) { throw 'Cannot read fixture bounds.' }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -lt 200 -or $height -lt 160 -or $width -gt 1000 -or $height -gt 1000) { throw 'Fixture bounds invalid.' }
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
try {
    $dc = $graphics.GetHdc()
    try {
        if (-not [FrankessoSmokeSnapshot]::PrintWindow($handle, $dc, 2)) { throw 'Cannot capture the Tk fixture.' }
    } finally { $graphics.ReleaseHdc($dc) }
    $hasCream = $false
    $hasInk = $false
    for ($y = 12; $y -lt $height -and -not ($hasCream -and $hasInk); $y += 5) {
        for ($x = 12; $x -lt $width; $x += 5) {
            $pixel = $bitmap.GetPixel($x, $y)
            if ($pixel.R -eq 250 -and $pixel.G -eq 242 -and $pixel.B -eq 228) { $hasCream = $true }
            if ($pixel.R -eq 10 -and $pixel.G -eq 9 -and $pixel.B -eq 9) { $hasInk = $true }
        }
    }
    if (-not ($hasCream -and $hasInk)) { throw 'Captured fixture did not contain both app palette colors.' }
    $bitmap.Save($OutputFile, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $graphics.Dispose()
    $bitmap.Dispose()
}

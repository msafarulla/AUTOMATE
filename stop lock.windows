Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class NoLock {
  [DllImport("kernel32.dll")]
  public static extern uint SetThreadExecutionState(uint esFlags);
  public const uint ES_CONTINUOUS = 0x80000000;
  public const uint ES_SYSTEM_REQUIRED = 0x00000001;
  public const uint ES_DISPLAY_REQUIRED = 0x00000002;
}
"@

[NoLock]::SetThreadExecutionState(
  [NoLock]::ES_CONTINUOUS -bor [NoLock]::ES_SYSTEM_REQUIRED -bor [NoLock]::ES_DISPLAY_REQUIRED
)

Write-Host "Lockout prevention active. Keep this PowerShell window open."
while ($true) { Start-Sleep -Seconds 3600 }
# Windows Task Scheduler Setup Script for S3 Backup Sync
# Run this script as Administrator in PowerShell

$TaskName = "S3BackupSync"
$ScriptPath = "E:\NeurotechHub\Programming\HubStorage"
$PythonExe = "E:\NeurotechHub\Programming\HubStorage\.venv\Scripts\python.exe"
$Arguments = "s3_backup_sync.py --config s3_backup_config.json"

Write-Host "Setting up Windows Task Scheduler for S3 Backup Sync..."
Write-Host "Script Directory: $ScriptPath"
Write-Host "Python Executable: $PythonExe"

try {
    # Create the action
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $ScriptPath

    # Create the trigger (daily at 2 AM, repeat every 6 hours)
    $Trigger = New-ScheduledTaskTrigger -Daily -At "2:00AM"
    $Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "2:00AM" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

    # Create the principal (run as current user with highest privileges)
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

    # Create settings
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Check if task already exists and remove it
    $ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($ExistingTask) {
        Write-Host "Removing existing task..."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    # Register the task
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

    Write-Host "✅ Task '$TaskName' created successfully!"
    Write-Host ""
    Write-Host "You can:"
    Write-Host "  - View it in Task Scheduler (taskschd.msc)"
    Write-Host "  - Run manually: Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host "  - Check status: Get-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""
    Write-Host "The task will run:"
    Write-Host "  - Daily at 2:00 AM"
    Write-Host "  - Repeat every 6 hours for 24 hours"
    Write-Host "  - Command: $PythonExe $Arguments"
    Write-Host "  - Working Directory: $ScriptPath"

} catch {
    Write-Error "Failed to create scheduled task: $_"
    Write-Host ""
    Write-Host "Please ensure you're running PowerShell as Administrator"
    Write-Host "You may need to run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
}

Read-Host "Press Enter to continue..."

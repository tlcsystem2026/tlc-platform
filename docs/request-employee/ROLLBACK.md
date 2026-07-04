# Rollback Procedure

## Software rollback
Use Git:
```powershell
git log --oneline
git checkout <previous_commit>
```

## Pilot output rollback
```powershell
.\scripts\request-pilot-rollback.ps1
```

## Data safety
Original files are stored under:
- `PDF`
- `Excel`

The rollback script only moves Output results to Archive. It does not touch original files.

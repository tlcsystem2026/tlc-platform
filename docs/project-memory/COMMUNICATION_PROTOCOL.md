# Communication Protocol

## For the user
Natural Chinese is enough. Short commands are acceptable:
- “下一版”
- “继续请求书系统”
- “更新WBS”
- “这个部署失败了”
The AI should resolve these against project memory and current verified baseline.

## For the AI
Before coding or packaging:
1. Read AI_HANDOVER.
2. Read CURRENT_STATE and DECISIONS.
3. Check latest verified build in BUILD_HISTORY.
4. Read KNOWN_ISSUES and NEXT_ACTIONS.
5. Check WBS.
6. Do not assume an unverified package is stable.

## When user says “下一版”
Required workflow:
current state -> stable baseline -> scope -> implementation -> static checks ->
tests -> regression -> package integrity -> deployment logic -> docs/WBS update -> delivery.

## When deployment fails
- Do not ask the user to manually patch multiple files unless emergency containment is explicitly requested.
- Identify root cause.
- Confirm rollback state.
- Add regression test for the exact failure.
- Strengthen preflight if the failure should have been caught before replacement.
- Update Build History and Known Issues.

## New chat opening message
Recommended user message:
“读取 TLC Project Memory 最新交接资料，继续项目。先复述当前状态、稳定版本、
三条主线、已知问题和下一步，不要直接改代码。”

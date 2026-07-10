# Build034 Migration Map

```text
原始销售请求书 Excel/PDF
        ↓
现有 Parser（优先复用）
        ↓
标准 RequestDocument
        ↓
现有 Compare API（兼容）
        ↓
CompareResult
   ├─ 有错误 → Error File + Web错误详情
   └─ 无错误 → Pending Review DB
                         ↓
              真实性/重复/取消审核
                         ↓
              正式销售请求书台账
                         ↓
银行CSV/Excel/PDF → 标准BankTransaction
                         ↓
按客户与两个截止日期过滤并对账
                         ↓
结清 / 部分入金 / 未付
                         ↓
结清后保存下一期请求截止日与银行入金截止日
```

# Domain Adapters for `fable-judge`

Thư mục này chứa các **fraud table theo domain** để `fable-judge.md` load khi đánh giá output không phải code.

## Cách dùng

`fable-judge.md` sẽ chọn adapter phù hợp với domain của task:

- Code / software engineering → `generic.md` (dùng bảng fraud chung)
- Data analysis / ML → `data.md`
- Infra / DevOps → `devops.md`
- Documentation / research → `research.md`

## Cấu trúc một adapter

Mỗi file `.md` là một bảng fraud với 2 cột:

| Fraud pattern | Evidence to hunt |
|---------------|------------------|
| ... | ... |

Xem `generic.md` làm mẫu.

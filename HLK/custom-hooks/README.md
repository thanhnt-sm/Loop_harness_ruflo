# HLK Custom Hooks

> Thư mục chứa business logic tùy biến của người dùng.
> Mọi hook đều phải tuân thủ hợp đồng (contract) dưới đây.

## Cấu trúc thư mục

```
HLK/custom-hooks/
├── pre-argv/          # Chạy trước khi loader sanitize process.argv
├── post-sanitize/     # Chạy sau khi loader sanitize process.argv
└── agent-tool/        # Chạy trong hlk-hook-bridge.mjs (agent runtime)
```

## Quy ước tên file

```
<order>-<mo-ta>.hook.mjs
```

Ví dụ:
- `10-block-internal-codename.hook.mjs`
- `20-log-audit-local.hook.mjs`

Số `order` quyết định thứ tự chạy trong cùng một phase.

## Hợp đồng export default

```js
/**
 * Hợp đồng bắt buộc cho mọi custom hook HLK.
 *
 * @param {object} context - ngữ cảnh tuỳ phase
 * @returns {Promise<{ value?: any, block?: boolean, reason?: string }>}
 *
 *   - value: giá trị đã biến đổi (nếu có)
 *   - block: true nếu muốn chặn hành động
 *   - reason: lý do chặn, hiển thị ra stderr
 */
export default async function run(context) {
  return { value: context.value };
}
```

## Context theo phase

### `pre-argv`

```js
context = { argv: process.argv }
// Có thể trả về { argv: [...] } để ghi đè process.argv
```

### `post-sanitize`

```js
context = { argv: process.argv }
// Không nên ghi đè process.argv trừ khi thực sự cần
```

### `agent-tool`

```js
context = {
  toolName: 'Bash',
  toolInput: { command: '...' },
  input: { /* JSON gốc từ stdin */ }
}
// Có thể trả về { block: true, reason: '...' } để chặn tool
```

## Nguyên tắc an toàn

1. **Lỗi kỹ thuật trong hook** → loader bỏ qua hook đó, không làm sập CLI.
2. **Hook chủ động trả `block: true`** → CLI dừng ngay với exit code 2.
3. **Không console.log secret** trong hook.
4. **Muốn log audit** thì dùng `process.stderr.write`.

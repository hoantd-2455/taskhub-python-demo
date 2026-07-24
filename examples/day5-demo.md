# Dữ liệu mẫu Day 5

Sau khi đã cấu hình `.env`, migrate database và chạy API, tạo dữ liệu mẫu bằng:

```bash
uv run python scripts/seed_example_data.py
```

Lệnh có thể chạy lại an toàn: email, workspace, project và các task mẫu không bị tạo trùng.
Toàn bộ tài khoản sau là dữ liệu giả, chỉ dành cho PostgreSQL local:

| Vai trò | Email đăng nhập | Mật khẩu |
| --- | --- | --- |
| ADMIN | `admin@taskhub.demo` | `TaskHubDemo123!` |
| OWNER | `owner@taskhub.demo` | `TaskHubDemo123!` |
| EDITOR | `editor@taskhub.demo` | `TaskHubDemo123!` |
| VIEWER | `viewer@taskhub.demo` | `TaskHubDemo123!` |
| Không thuộc workspace | `outsider@taskhub.demo` | `TaskHubDemo123!` |

Trong Swagger, gọi `POST /api/v1/auth/login`, điền email vào trường `username`, rồi bấm
**Authorize** với access token nhận được. Dữ liệu mẫu có project `RBAC and Filtering` trong
workspace `TaskHub Day 5 Demo`.
API `GET /api/v1/labels` sẽ trả về hai label mẫu: `backend` và `security`.

Thử các tình huống sau:

1. Với `viewer`, gọi `GET /api/v1/tasks?status=TODO&page=1&limit=2`: thành công.
2. Với `viewer`, gọi `POST /api/v1/projects/{project_id}/tasks`: nhận `403`.
3. Với `editor`, gọi cùng API `POST`: thành công nếu `assignee_id` là owner/editor/viewer.
4. Với `outsider`, gọi `GET /api/v1/projects/{project_id}/tasks`: nhận `403`.
5. Với `admin`, gọi `GET /api/v1/tasks`: nhìn thấy toàn bộ task, kể cả ngoài membership.

Response list có dạng:

```json
{
  "items": [],
  "total": 4,
  "page": 1,
  "limit": 20
}
```

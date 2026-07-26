# Day 6: giao dịch, gán việc và bình luận

Tài liệu này dùng với dữ liệu local tạo bởi `uv run python scripts/seed_example_data.py`.
Script có thể chạy lại nhiều lần mà không tạo trùng dữ liệu.

## Tài khoản giả

Mật khẩu chung (chỉ dùng local): `TaskHubDemo123!`

| Email | Vai trò | Mục đích thử nghiệm |
| --- | --- | --- |
| `admin@taskhub.demo` | ADMIN | Gán việc và xóa mọi bình luận hợp lệ. |
| `owner@taskhub.demo` | OWNER | Quản lý task và xóa bình luận trong workspace. |
| `editor@taskhub.demo` | EDITOR | Gán việc, thêm bình luận và xóa bình luận của mình. |
| `viewer@taskhub.demo` | VIEWER | Chỉ đọc; không gán việc hoặc tạo bình luận. |
| `outsider@taskhub.demo` | Không là thành viên | Kiểm tra bị từ chối khi truy cập workspace. |

Workspace `TaskHub Day 5 Demo` có project `RBAC and Filtering`. Task `Review API permissions`
đã có sẵn một bình luận của editor để quan sát dữ liệu quan hệ.

## Chuẩn bị token trong Swagger

1. Gọi `POST /api/v1/auth/login`, điền email vào trường `username` và mật khẩu ở trên.
2. Sao chép `access_token` từ response.
3. Nhấn **Authorize** và dán access token.
4. Gọi `GET /api/v1/projects/{project_id}/tasks` để lấy `task_id` cần thử.

## Thử các endpoint Day 6

### Gán người phụ trách

Gọi `POST /api/v1/tasks/{task_id}/assign` bằng token owner hoặc editor:

```json
{
  "assignee_id": 3
}
```

Người được gán phải là thành viên của workspace. Thử `assignee_id` của `outsider@taskhub.demo`
sẽ nhận `422`; dùng token viewer sẽ nhận `403`.

### Thêm bình luận

Gọi `POST /api/v1/tasks/{task_id}/comments` bằng owner hoặc editor:

```json
{
  "content": "Đã kiểm tra quy tắc phân quyền, có thể tiếp tục review."
}
```

API trả `201 Created` cùng thông tin bình luận. Viewer không được tạo bình luận.

### Xóa bình luận

Gọi `DELETE /api/v1/tasks/{task_id}/comments/{comment_id}`. Tác giả của bình luận, workspace
owner và admin có thể xóa. Editor khác tác giả và viewer khác tác giả nhận `403`. Nếu `comment_id`
không thuộc `task_id` trên URL, API trả `404` để tránh xóa nhầm bình luận của task khác.

## Ý nghĩa transaction

Thao tác tạo, gán và xóa đều chỉ hoàn tất sau khi database `commit`. Nếu database báo lỗi, API
`rollback` transaction trước khi trả lỗi; nhờ vậy không để lại thay đổi dở dang.

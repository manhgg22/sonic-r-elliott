# Frontend architecture

Sonic R dùng cấu trúc **feature-first**: code thuộc một màn hình nằm cùng feature,
code được nhiều feature sử dụng mới đưa vào `components` hoặc `shared`.

```text
src/
├─ app/                    # App shell, routing/page state, bootstrap
├─ components/
│  ├─ layout/              # Sidebar, topbar và layout dùng toàn ứng dụng
│  ├─ trading/             # Component giao dịch dùng ở nhiều feature
│  └─ ui/                  # Primitive UI không chứa nghiệp vụ
├─ features/
│  ├─ terminal/            # Tổng quan thị trường
│  ├─ scanner/             # Bộ quét tín hiệu
│  ├─ signal/              # Chi tiết thiết lập
│  ├─ portfolio/           # Danh mục và quản trị rủi ro
│  ├─ history/             # Sổ lệnh và lifecycle audit
│  └─ system/              # API/WebSocket console
├─ hooks/                  # React hooks dùng chung
├─ services/               # REST/WebSocket client và tích hợp bên ngoài
├─ shared/                 # Types, constants, formatter thuần
└─ styles/                 # Global styles và library overrides
```

## Quy tắc đặt code

- Component chỉ dùng trong một feature: đặt bên trong feature đó.
- Component dùng từ hai feature trở lên: đặt trong `components`.
- Không gọi API trực tiếp trong component UI; khai báo trong `services`.
- Type dùng chung đặt trong `shared/types.ts`.
- Formatter và helper phải là hàm thuần, đặt trong `shared`.
- `app/App.tsx` chỉ điều phối state cấp ứng dụng và chọn page; không chứa UI của page.
- Tránh tạo file barrel `index.ts` nếu chưa cần, để import rõ nguồn và tránh dependency cycle.

## Lệnh phát triển

```powershell
# Backend, chạy từ repository root
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm.cmd run dev

# Kiểm tra production build
npm.cmd run build
```

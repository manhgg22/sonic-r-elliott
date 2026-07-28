import { Pagination } from "antd";

export function TablePager({ page, pageSize, total, onChange }: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number, pageSize: number) => void;
}) {
  if (!total) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="table-pager">
      <span>Hiển thị {start}–{end} / {total}</span>
      <Pagination
        current={page}
        pageSize={pageSize}
        total={total}
        showSizeChanger
        pageSizeOptions={[10, 20, 50, 100]}
        responsive
        onChange={onChange}
      />
    </div>
  );
}

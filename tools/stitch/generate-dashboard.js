import { writeFile } from "node:fs/promises";
import { stitch } from "@google/stitch-sdk";

const projectId = process.env.STITCH_PROJECT_ID;
if (!process.env.STITCH_API_KEY && !process.env.STITCH_ACCESS_TOKEN) {
  throw new Error("Cần STITCH_API_KEY hoặc STITCH_ACCESS_TOKEN.");
}
if (!projectId) {
  throw new Error("Cần STITCH_PROJECT_ID.");
}

const prompt = `
Thiết kế dashboard giao dịch crypto Sonic R bằng tiếng Việt cho desktop.
Đây là công cụ vận hành, không phải landing page. Ưu tiên mật độ thông tin,
khả năng quét nhanh và phân biệt LONG/SHORT. Có sidebar lọc rủi ro, thanh trạng
thái monitor, KPI thị trường, danh sách tín hiệu, vị thế mở, biểu đồ nến với
EMA34/EMA89 và Entry/SL/TP, bảng lịch sử. Phong cách sáng, trung tính, chuyên
nghiệp; xanh lá cho LONG, đỏ cho SHORT; góc vuông nhẹ; không gradient, không
hero marketing, không card lồng card. Bố cục phải responsive và không để chữ
tràn hoặc chồng lên nhau.
`;

const project = stitch.project(projectId);
const screen = await project.generate(prompt, "DESKTOP");
const result = {
  projectId,
  screenId: screen.id,
  htmlUrl: await screen.getHtml(),
  imageUrl: await screen.getImage(),
};

await writeFile(
  new URL("./last-generation.json", import.meta.url),
  JSON.stringify(result, null, 2),
);
console.log(JSON.stringify(result, null, 2));

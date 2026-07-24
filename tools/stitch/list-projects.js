import { stitch } from "@google/stitch-sdk";

const projects = await stitch.projects();
const result = [];
for (const project of projects) {
  const screens = await project.screens();
  result.push({
    projectId: project.id,
    screenCount: screens.length,
  });
}
console.log(JSON.stringify(result, null, 2));

import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryProtoRoot = resolve(scriptDirectory, "../../../proto");
const distributionProtoRoot = resolve(scriptDirectory, "../dist/proto");

// Keep the published gRPC package self-contained while copying only the
// service definitions and their transitive imports used by its clients.
const protoFiles = [
  "common/pagination.proto",
  "data/v1/service.proto",
  "data/v1/types.proto",
  "ecocredit/v1/service.proto",
  "ecocredit/v1/types.proto",
];

for (const relativePath of protoFiles) {
  const sourcePath = resolve(repositoryProtoRoot, relativePath);
  const destinationPath = resolve(distributionProtoRoot, relativePath);
  mkdirSync(dirname(destinationPath), { recursive: true });
  copyFileSync(sourcePath, destinationPath);
}

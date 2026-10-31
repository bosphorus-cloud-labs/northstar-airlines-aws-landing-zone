import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import openapiTS from "openapi-typescript";
const root = fileURLToPath(new URL("../../", import.meta.url));
// Test responses are generated from the real read-only backend, not a second policy model.
const python = `
import json
from fastapi.testclient import TestClient
from backend.app import create_app
schema = create_app().openapi()
fixtures = {}
with TestClient(create_app(local_demo=True), base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
    for path in ['/api/v1/summary', '/api/v1/accounts', '/api/v1/findings', '/api/v1/deployments', '/api/v1/drift', '/api/v1/exceptions', '/api/v1/accounts/sim-account-001', '/api/v1/accounts/sim-account-002']:
        params = {'at': '2026-10-31T12:00:00Z'}
        if path in ['/api/v1/accounts', '/api/v1/findings', '/api/v1/deployments', '/api/v1/drift', '/api/v1/exceptions']:
            params['limit'] = 100
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        fixtures[path] = response.json()
print(json.dumps({'schema': schema, 'fixtures': fixtures}))
`;
const { schema, fixtures } = JSON.parse(
  execFileSync(`${root}.venv/bin/python`, ["-c", python], {
    cwd: root,
    encoding: "utf8",
  }),
);
const outputs = [
  [new URL("../src/api/schema.d.ts", import.meta.url), await openapiTS(schema)],
  [
    new URL("../src/test/api-responses.json", import.meta.url),
    `${JSON.stringify(fixtures, null, 2)}\n`,
  ],
];
for (const [output, content] of outputs) {
  if (process.argv.includes("--check")) {
    if (readFileSync(output, "utf8") !== content)
      throw new Error(
        "Generated contracts or test responses differ. Run npm run api:generate.",
      );
  } else writeFileSync(output, content);
}
if (process.argv.includes("--check"))
  console.log("API types and test responses match the backend.");

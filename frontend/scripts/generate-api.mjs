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
from types import SimpleNamespace
from backend.deployment.resources import view
from tests.resource_fixtures import load as frozen_resources
# Contract examples are frozen test scenarios, not a second runtime data source.
resource_repository = SimpleNamespace(read=lambda: view(frozen_resources()))
with TestClient(create_app(local_demo=True, resource_repository=resource_repository), base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
    resource_response = client.get('/api/v1/summary?view=resources')
    assert resource_response.status_code == 200
    resources = resource_response.json()
fixtures = {}
with TestClient(create_app(local_demo=True), base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
    for path in ['/api/v1/summary', '/api/v1/accounts', '/api/v1/findings', '/api/v1/deployments', '/api/v1/drift', '/api/v1/exceptions', '/api/v1/accounts/sim-account-001', '/api/v1/accounts/sim-account-002']:
        params = {'at': '2026-10-31T12:00:00Z'}
        if path in ['/api/v1/accounts', '/api/v1/findings', '/api/v1/deployments', '/api/v1/drift', '/api/v1/exceptions']:
            params['limit'] = 100
        response = client.get(path, params=params)
        assert response.status_code == 200, path
        fixtures[path] = response.json()
with TestClient(create_app(local_demo=True), base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
    response = client.get('/api/v1/summary', params={'catalog': 'true'})
    assert response.status_code == 200
    fixtures['/api/v1/summary?catalog=true'] = response.json()
from tests.fixture_versions import catalogue
version_fixtures = {}
with TestClient(create_app(local_demo=True, catalog=catalogue()), base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
    for version in ['1.0.0', '2.0.0']:
        records = {}
        for path in ['/api/v1/summary', '/api/v1/accounts', '/api/v1/findings', '/api/v1/deployments', '/api/v1/drift', '/api/v1/exceptions', '/api/v1/accounts/sim-account-011']:
            params = {'policy_version': version}
            if path == '/api/v1/summary': params['catalog'] = 'true'
            elif path != '/api/v1/accounts/sim-account-011': params['limit'] = 100
            response = client.get(path, params=params)
            assert response.status_code in [200, 404]
            records[path] = response.json()
        version_fixtures[version] = records
print(json.dumps({'schema': schema, 'fixtures': fixtures, 'versions': version_fixtures, 'resources': resources}))
`;
const { schema, fixtures, versions, resources } = JSON.parse(
  execFileSync(`${root}.venv/bin/python`, ["-c", python], {
    cwd: root,
    encoding: "utf8",
  }),
);
const outputs = [
  [
    new URL("../src/test/resource-responses.json", import.meta.url),
    `${JSON.stringify(resources, null, 2)}\n`,
  ],
  [new URL("../src/api/schema.d.ts", import.meta.url), await openapiTS(schema)],
  [
    new URL("../src/test/api-responses.json", import.meta.url),
    `${JSON.stringify(fixtures, null, 2)}\n`,
  ],
  [
    new URL("../src/test/version-responses.json", import.meta.url),
    `${JSON.stringify(versions, null, 2)}\n`,
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

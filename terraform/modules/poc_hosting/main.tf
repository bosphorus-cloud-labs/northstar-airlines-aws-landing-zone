# Manual static hosting first. GitHub authorization is never stored in Terraform.
resource "aws_amplify_app" "console" {
  name                     = var.name
  platform                 = "WEB"
  enable_branch_auto_build = false
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }
  custom_headers = <<-HEADERS
    customHeaders:
      - pattern: '**'
        headers:
          - key: Content-Security-Policy
            value: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://*.execute-api.eu-central-1.amazonaws.com https://cognito-idp.eu-central-1.amazonaws.com https://*.auth.eu-central-1.amazoncognito.com; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' https://*.auth.eu-central-1.amazoncognito.com"
          - key: X-Content-Type-Options
            value: nosniff
          - key: Referrer-Policy
            value: no-referrer
          - key: X-Frame-Options
            value: DENY
          - key: Strict-Transport-Security
            value: max-age=31536000;includeSubDomains
  HEADERS
  tags           = var.tags
  lifecycle { ignore_changes = [repository] }
}

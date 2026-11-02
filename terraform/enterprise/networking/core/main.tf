resource "aws_ec2_transit_gateway" "central" {
  description                     = "NorthStar centrally owned transit gateway"
  amazon_side_asn                 = var.amazon_side_asn
  auto_accept_shared_attachments  = "disable"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"
  tags                            = { Name = "northstar-central" }
  lifecycle { prevent_destroy = true }
}

resource "aws_ec2_transit_gateway_route_table" "environment" {
  for_each           = toset(["production", "development", "inspection"])
  transit_gateway_id = aws_ec2_transit_gateway.central.id
  tags               = { Name = "northstar-${each.key}" }
  lifecycle { prevent_destroy = true }
}

resource "aws_ram_resource_share" "transit_gateway" {
  name                      = "northstar-central-transit-gateway"
  allow_external_principals = false
  lifecycle { prevent_destroy = true }
}

resource "aws_ram_resource_association" "transit_gateway" {
  resource_arn       = aws_ec2_transit_gateway.central.arn
  resource_share_arn = aws_ram_resource_share.transit_gateway.arn
}

resource "aws_ram_principal_association" "organization" {
  principal          = var.organization_arn
  resource_share_arn = aws_ram_resource_share.transit_gateway.arn
}

resource "aws_ec2_transit_gateway_vpc_attachment" "inspection" {
  subnet_ids                                      = var.inspection_transit_gateway_subnet_ids
  transit_gateway_id                              = aws_ec2_transit_gateway.central.id
  vpc_id                                          = var.inspection_vpc_id
  appliance_mode_support                          = "enable"
  dns_support                                     = "enable"
  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false
  tags                                            = { Name = "northstar-inspection" }
  lifecycle { prevent_destroy = true }
}

resource "aws_ec2_transit_gateway_route_table_association" "inspection" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment["inspection"].id
}

resource "aws_ec2_transit_gateway_route" "environment_to_inspection" {
  for_each                       = var.inspection_routes
  destination_cidr_block         = each.value.destination_cidr
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment[each.value.environment].id
}

# Attachments are created in workload-account states, then accepted and routed
# here so the network account remains the sole owner of TGW route tables.
resource "aws_ec2_transit_gateway_vpc_attachment_accepter" "workload" {
  for_each                      = var.workload_attachments
  transit_gateway_attachment_id = each.value.attachment_id
  tags                          = { Name = "northstar-${each.value.environment}-${each.key}" }
  lifecycle { prevent_destroy = true }
}

resource "aws_ec2_transit_gateway_route_table_association" "workload" {
  for_each                       = var.workload_attachments
  transit_gateway_attachment_id  = each.value.attachment_id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment[each.value.environment].id
  depends_on                     = [aws_ec2_transit_gateway_vpc_attachment_accepter.workload]
}

resource "aws_ec2_transit_gateway_route" "inspection_return_to_workload" {
  for_each                       = var.inspection_return_routes
  destination_cidr_block         = each.value.vpc_cidr
  transit_gateway_attachment_id  = var.workload_attachments[each.value.attachment_key].attachment_id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment["inspection"].id
}

resource "aws_customer_gateway" "hybrid" {
  bgp_asn    = var.customer_gateway_bgp_asn
  ip_address = var.customer_gateway_ip
  type       = "ipsec.1"
  tags       = { Name = "northstar-hybrid" }
}

resource "aws_vpn_connection" "hybrid" {
  customer_gateway_id = aws_customer_gateway.hybrid.id
  transit_gateway_id  = aws_ec2_transit_gateway.central.id
  type                = "ipsec.1"
  static_routes_only  = false
  tags                = { Name = "northstar-hybrid" }
  lifecycle { prevent_destroy = true }
}

resource "aws_ec2_transit_gateway_route_table_association" "hybrid" {
  transit_gateway_attachment_id  = aws_vpn_connection.hybrid.transit_gateway_attachment_id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment["inspection"].id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "hybrid" {
  for_each                       = var.direct_hybrid_route_environments
  transit_gateway_attachment_id  = aws_vpn_connection.hybrid.transit_gateway_attachment_id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.environment[each.key].id
}

resource "aws_lb" "inspection" {
  name                             = "northstar-inspection-gwlb"
  load_balancer_type               = "gateway"
  subnets                          = var.inspection_gwlb_subnet_ids
  enable_cross_zone_load_balancing = true
}

resource "aws_lb_target_group" "inspection" {
  name        = "northstar-inspection"
  port        = 6081
  protocol    = "GENEVE"
  target_type = "ip"
  vpc_id      = var.inspection_vpc_id
  health_check {
    protocol = "TCP"
    port     = var.appliance_health_check_port
  }
}

resource "aws_lb_listener" "inspection" {
  load_balancer_arn = aws_lb.inspection.arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.inspection.arn
  }
}

resource "aws_vpc_endpoint_service" "inspection" {
  acceptance_required        = true
  gateway_load_balancer_arns = [aws_lb.inspection.arn]
  allowed_principals         = var.endpoint_service_allowed_principal_arns
}

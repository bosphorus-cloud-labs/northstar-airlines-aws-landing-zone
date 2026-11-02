resource "aws_ec2_transit_gateway_vpc_attachment" "workload" {
  subnet_ids         = var.transit_gateway_subnet_ids
  transit_gateway_id = var.transit_gateway_id
  vpc_id             = var.vpc_id
  dns_support        = "enable"
  tags               = { Name = "northstar-${var.environment}-workload", Environment = title(var.environment) }
  lifecycle { prevent_destroy = true }
}

resource "aws_route" "approved_transit_gateway" {
  for_each               = var.approved_routes
  route_table_id         = each.value.route_table_id
  destination_cidr_block = each.value.destination_cidr
  transit_gateway_id     = var.transit_gateway_id
  depends_on             = [aws_ec2_transit_gateway_vpc_attachment.workload]
}

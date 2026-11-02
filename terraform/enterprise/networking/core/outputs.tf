output "transit_gateway_id" { value = aws_ec2_transit_gateway.central.id }
output "route_table_ids" { value = { for environment, table in aws_ec2_transit_gateway_route_table.environment : environment => table.id } }
output "inspection_attachment_id" { value = aws_ec2_transit_gateway_vpc_attachment.inspection.id }
output "gwlb_endpoint_service_name" { value = aws_vpc_endpoint_service.inspection.service_name }
output "vpn_connection_id" { value = aws_vpn_connection.hybrid.id }

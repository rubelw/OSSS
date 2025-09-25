primary_datacenter = "dc1"
node_name   = "consul-1"
data_dir    = "/consul/data"     # matches your volume mount
bind_addr   = "0.0.0.0"
client_addr = "0.0.0.0"

# Single-container server (dev-ish). For a client, set server = false.
server            = true
bootstrap_expect  = 1

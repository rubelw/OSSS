acl {
  enabled                  = true
  default_policy           = "deny"
  enable_token_persistence = true
  tokens {
    initial_management = "password"
    agent = "password"
    default = "password"
  }
}


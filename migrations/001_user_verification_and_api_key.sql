ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deepseek_api_key_encrypted TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS deepseek_api_key_hint VARCHAR(16);

CREATE TABLE IF NOT EXISTS email_verification_codes (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  code_hash VARCHAR(64) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_email_verification_codes_user_id ON email_verification_codes(user_id);

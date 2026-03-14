"""JSON schema strings and examples derived from WorkItem Pydantic models.

These constants are used inside prompt templates to instruct the LLM on the
exact shape of the expected JSON output.
"""

from __future__ import annotations

WORK_ITEM_HIERARCHY_SCHEMA = '''{
  "type": "object",
  "title": "WorkItemHierarchy",
  "description": "Top-level response containing a list of work items.",
  "properties": {
    "items": {
      "type": "array",
      "description": "Root-level work items",
      "items": {
        "$ref": "#/$defs/WorkItem"
      }
    }
  },
  "required": ["items"],
  "$defs": {
    "WorkItemType": {
      "type": "string",
      "enum": ["epic", "story", "bug", "task"],
      "description": "Supported work-item types."
    },
    "WorkItem": {
      "type": "object",
      "title": "WorkItem",
      "description": "A single work item in the hierarchy.",
      "properties": {
        "type": {
          "$ref": "#/$defs/WorkItemType",
          "description": "The type of work item"
        },
        "title": {
          "type": "string",
          "description": "Short title for the work item (max 80 characters)"
        },
        "description": {
          "type": "string",
          "default": "",
          "description": "Detailed description or acceptance criteria (min 20 characters)"
        },
        "labels": {
          "type": "array",
          "items": {"type": "string"},
          "default": [],
          "description": "Lowercase slug labels (e.g. backend, api, auth)"
        },
        "children": {
          "type": "array",
          "items": {"$ref": "#/$defs/WorkItem"},
          "default": [],
          "description": "Nested child work items (max depth 3: epic -> story -> task)"
        }
      },
      "required": ["type", "title", "description", "labels"]
    }
  }
}'''

WORK_ITEM_SCHEMA = '''{
  "$ref": "#/$defs/WorkItem",
  "$defs": {
    "WorkItem": {
      "type": "object",
      "title": "WorkItem",
      "description": "A single work item in the hierarchy.",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["epic", "story", "bug", "task"],
          "description": "The type of work item"
        },
        "title": {
          "type": "string",
          "description": "Short title for the work item (max 80 characters)"
        },
        "description": {
          "type": "string",
          "default": "",
          "description": "Detailed description or acceptance criteria (min 20 characters)"
        },
        "labels": {
          "type": "array",
          "items": {"type": "string"},
          "default": [],
          "description": "Lowercase slug labels (e.g. backend, api, auth)"
        },
        "children": {
          "type": "array",
          "items": {"$ref": "#/$defs/WorkItem"},
          "default": [],
          "description": "Nested child work items"
        }
      },
      "required": ["type", "title", "description", "labels"]
    }
  }
}'''

WORK_ITEM_HIERARCHY_EXAMPLE = '''{
  "items": [
    {
      "type": "epic",
      "title": "User Authentication System",
      "description": "Implement a complete authentication system supporting email/password and OAuth2 social login providers with JWT session management.",
      "labels": ["auth", "security", "backend"],
      "children": [
        {
          "type": "story",
          "title": "Implement JWT token generation and validation",
          "description": "Create stateless JWT access tokens (15 min TTL) and refresh tokens (7 day TTL). Implement signing with RS256, token validation middleware, and automatic refresh rotation.",
          "labels": ["auth", "backend", "api"],
          "children": [
            {
              "type": "task",
              "title": "Add RSA key pair generation for JWT signing",
              "description": "Generate and securely store RS256 key pairs. Load private key from environment variable LLM_JWT_PRIVATE_KEY at startup.",
              "labels": ["auth", "security", "backend"],
              "children": []
            },
            {
              "type": "task",
              "title": "Create token validation middleware",
              "description": "FastAPI dependency that extracts the Bearer token from Authorization header, validates signature, checks expiry, and injects the user identity into the request context.",
              "labels": ["auth", "middleware", "backend"],
              "children": []
            }
          ]
        },
        {
          "type": "story",
          "title": "Build OAuth2 social login with GitHub and Google",
          "description": "Integrate GitHub and Google OAuth2 flows using the authlib library. Handle callback, create or link user accounts, and issue app JWT tokens on successful login.",
          "labels": ["auth", "oauth2", "backend"],
          "children": [
            {
              "type": "task",
              "title": "Configure OAuth2 providers in settings",
              "description": "Add GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET to ProviderConfig. Validate presence at startup.",
              "labels": ["config", "auth"],
              "children": []
            }
          ]
        },
        {
          "type": "bug",
          "title": "Fix password reset token reuse after expiry",
          "description": "Password reset tokens remain usable after their 1-hour expiry window if the user resets once. Tokens must be invalidated on first use and expire correctly.",
          "labels": ["auth", "bug", "security"],
          "children": []
        }
      ]
    }
  ]
}'''

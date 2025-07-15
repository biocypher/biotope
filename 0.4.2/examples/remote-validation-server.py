#!/usr/bin/env python3
"""
Example Flask server for serving remote validation configurations.

This demonstrates how to set up a simple HTTP server to provide
validation configurations for biotope projects.

Usage:
    python remote-validation-server.py

Then in your biotope project:
    biotope config set-remote-validation --url http://localhost:5000/validation.yaml
"""

from flask import Flask, send_file
import yaml
from pathlib import Path

app = Flask(__name__)

# Example validation configurations for different use cases
VALIDATION_CONFIGS = {
    "basic": {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description",
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    },
    "comprehensive": {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description",
                "creator",
                "dateCreated",
                "distribution",
                "license",
                "version",
                "citation"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 20},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
                "license": {"type": "string", "min_length": 5},
                "version": {"type": "string", "min_length": 1},
                "citation": {"type": "string", "min_length": 10}
            }
        }
    },
    "clinical": {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description",
                "creator",
                "dateCreated",
                "distribution",
                "license",
                "ethics_approval",
                "data_usage_agreement"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 50},
                "creator": {"type": "object", "required_keys": ["name", "institution"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
                "license": {"type": "string", "min_length": 5},
                "ethics_approval": {"type": "string", "min_length": 1},
                "data_usage_agreement": {"type": "string", "min_length": 1}
            }
        }
    }
}


@app.route('/')
def index():
    """Show available validation configurations."""
    html = """
    <h1>Biotope Remote Validation Server</h1>
    <p>Available validation configurations:</p>
    <ul>
        <li><a href="/validation.yaml">Default validation</a></li>
        <li><a href="/basic/validation.yaml">Basic validation</a></li>
        <li><a href="/comprehensive/validation.yaml">Comprehensive validation</a></li>
        <li><a href="/clinical/validation.yaml">Clinical data validation</a></li>
    </ul>
    <p>Usage in biotope project:</p>
    <code>biotope config set-remote-validation --url http://localhost:5000/validation.yaml</code>
    """
    return html


@app.route('/validation.yaml')
def default_validation():
    """Serve the default validation configuration."""
    return yaml.dump(VALIDATION_CONFIGS["basic"], default_flow_style=False), 200, {
        'Content-Type': 'application/x-yaml'
    }


@app.route('/<config_type>/validation.yaml')
def specific_validation(config_type):
    """Serve a specific validation configuration."""
    if config_type not in VALIDATION_CONFIGS:
        return f"Configuration '{config_type}' not found", 404
    
    return yaml.dump(VALIDATION_CONFIGS[config_type], default_flow_style=False), 200, {
        'Content-Type': 'application/x-yaml'
    }


@app.route('/health')
def health():
    """Health check endpoint."""
    return {"status": "healthy", "configurations": list(VALIDATION_CONFIGS.keys())}


if __name__ == '__main__':
    print("Starting Biotope Remote Validation Server...")
    print("Available configurations:")
    for config_name in VALIDATION_CONFIGS.keys():
        print(f"  - {config_name}")
    print("\nUsage in biotope project:")
    print("  biotope config set-remote-validation --url http://localhost:5000/validation.yaml")
    print("\nServer starting on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000) 
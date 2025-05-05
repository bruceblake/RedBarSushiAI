"""
Monitoring routes for RedBarSushiAI.
This module provides endpoints for metrics, health checks, and monitoring.
"""

from flask import Blueprint, jsonify, request, Response, current_app
import logging
import json
import time
import os
from datetime import datetime

from app.utils.monitoring import get_metrics_snapshot
from app.utils.agent_monitoring import api_monitoring

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
monitoring_bp = Blueprint("monitoring", __name__)

@monitoring_bp.route("/metrics", methods=["GET"])
@api_monitoring(endpoint="metrics")
def metrics():
    """
    Return a snapshot of metrics for monitoring dashboards.
    
    Returns:
        JSON response with metrics data
    """
    try:
        # Check if Prometheus exporter is available
        try:
            from prometheus_client import generate_latest
            # Return Prometheus metrics if available
            return Response(generate_latest(), mimetype="text/plain")
        except ImportError:
            # Fall back to our internal metrics
            metrics_data = get_metrics_snapshot()
            return jsonify(metrics_data)
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to generate metrics",
            "timestamp": datetime.now().isoformat()
        }), 500

@monitoring_bp.route("/health", methods=["GET"])
@api_monitoring(endpoint="health")
def health():
    """
    Enhanced health check with component status.
    
    Returns:
        JSON response with health data
    """
    # Basic health information
    health_info = {
        "status": "ok",
        "message": "RedBarSushiAI is running",
        "timestamp": datetime.now().isoformat(),
        "environment": (
            "staging"
            if os.environ.get("FLASK_ENV") == "staging"
            or os.environ.get("IS_STAGING")
            else (
                "production" if os.environ.get("RENDER", False) else "development"
            )
        ),
        "components": {},
    }
    
    # Check database connection
    try:
        # Simple database ping with proper session handling
        with current_app.app_context():
            # Import from db_init to use our fresh session logic
            from app.db_init import fresh_session, verify_connection

            # Ensure we have a fresh session
            fresh_session()

            # Use our verify_connection function that handles session lifecycle
            if verify_connection():
                health_info["components"]["database"] = {
                    "status": "ok",
                    "message": "Connected to database"
                }
            else:
                health_info["components"]["database"] = {
                    "status": "error",
                    "message": "Connection verification failed"
                }
                health_info["status"] = "degraded"
    except Exception as e:
        health_info["components"]["database"] = {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
        health_info["status"] = "degraded"

    # Check Redis with improved connection handling
    # Always prioritize REDIS_URL over CELERY_BROKER_URL
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
    if redis_url:
        try:
            import redis

            # Ensure the URL has the proper redis:// prefix
            if not redis_url.startswith("redis://"):
                redis_url = f"redis://{redis_url}"
                
            r = redis.from_url(redis_url, socket_timeout=2.0)
            r.ping()
            
            # Make a safe URL for logging by hiding hostname/credentials
            safe_url = redis_url.replace(redis_url.split("@")[-1] if "@" in redis_url else redis_url, "*****")
            
            health_info["components"]["redis"] = {
                "status": "ok",
                "message": f"Connected to Redis at {safe_url}"
            }
        except Exception as e:
            health_info["components"]["redis"] = {
                "status": "error",
                "message": f"Error: {str(e)}"
            }
            # Redis issues shouldn't mark the whole system as down
            if health_info["status"] == "ok":
                health_info["status"] = "degraded"

    # Check menu data
    try:
        from app.utils.menu_utils_db import load_menu_data

        menu = load_menu_data()
        items_count = len(menu.get("items", []))
        health_info["components"]["menu"] = {
            "status": "ok",
            "message": f"Menu loaded with {items_count} items"
        }
    except Exception as e:
        health_info["components"]["menu"] = {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
        if health_info["status"] == "ok":
            health_info["status"] = "degraded"
    
    # Check OpenAI API connection
    try:
        from app.utils.agents_sdk import agents_client
        
        if agents_client:
            health_info["components"]["openai_agents_sdk"] = {
                "status": "ok",
                "message": "OpenAI Agents SDK client initialized"
            }
        else:
            health_info["components"]["openai_agents_sdk"] = {
                "status": "error",
                "message": "OpenAI Agents SDK client not initialized"
            }
            if health_info["status"] == "ok":
                health_info["status"] = "degraded"
    except Exception as e:
        health_info["components"]["openai_agents_sdk"] = {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
        if health_info["status"] == "ok":
            health_info["status"] = "degraded"
    
    # Check agent factory status
    try:
        from app.agents.factory import agent_factory
        
        frontline_agent = agent_factory.get_frontline_agent()
        if frontline_agent:
            health_info["components"]["agent_factory"] = {
                "status": "ok",
                "message": "Agent factory initialized with frontline agent"
            }
        else:
            health_info["components"]["agent_factory"] = {
                "status": "error",
                "message": "Frontline agent not initialized"
            }
            if health_info["status"] == "ok":
                health_info["status"] = "degraded"
    except Exception as e:
        health_info["components"]["agent_factory"] = {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
        if health_info["status"] == "ok":
            health_info["status"] = "degraded"

    # Add metrics summary
    try:
        metrics_data = get_metrics_snapshot()
        # Include only high-level metrics
        health_info["metrics"] = {
            "counters_count": len(metrics_data.get("counters", {})),
            "histograms_count": len(metrics_data.get("histograms", {})),
            "timers_count": len(metrics_data.get("timers", {})),
            "gauges_count": len(metrics_data.get("gauges", {}))
        }
    except Exception as e:
        health_info["metrics"] = {
            "status": "error",
            "message": f"Error fetching metrics: {str(e)}"
        }
    
    return jsonify(health_info)

@monitoring_bp.route("/agents/health", methods=["GET"])
@api_monitoring(endpoint="agents_health")
def agents_health():
    """
    Health check for agent system.
    
    Returns:
        JSON response with agent health data
    """
    agent_health = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "agents": {}
    }
    
    try:
        from app.agents.factory import agent_factory
        
        # Check each agent
        for agent_name in ["frontline", "menu", "cart", "fulfillment", "guardrail", "escalation"]:
            agent = agent_factory.get_agent(agent_name)
            if agent:
                agent_id = getattr(agent, "agent_id", None)
                agent_health["agents"][agent_name] = {
                    "status": "ok",
                    "agent_id": agent_id,
                    "message": f"{agent.name} agent initialized"
                }
            else:
                agent_health["agents"][agent_name] = {
                    "status": "not_initialized",
                    "message": f"{agent_name} agent not initialized"
                }
                if agent_name in ["frontline", "menu", "cart"]:  # These are critical
                    agent_health["status"] = "degraded"
    except Exception as e:
        agent_health["status"] = "error"
        agent_health["message"] = f"Error checking agent health: {str(e)}"
    
    return jsonify(agent_health)

@monitoring_bp.route("/debug/threads", methods=["GET"])
@api_monitoring(endpoint="debug_threads")
def debug_threads():
    """
    Debug route to view active threads.
    Only available in development environment.
    
    Returns:
        JSON response with thread data
    """
    # Security check - only allow in development
    if os.environ.get("FLASK_ENV") not in ["development", "staging"]:
        return jsonify({
            "status": "error",
            "message": "This endpoint is only available in development environment"
        }), 403
    
    try:
        import threading
        
        # Get all active threads
        threads = threading.enumerate()
        thread_info = []
        
        for thread in threads:
            thread_info.append({
                "name": thread.name,
                "id": thread.ident,
                "daemon": thread.daemon,
                "alive": thread.is_alive()
            })
        
        return jsonify({
            "status": "ok",
            "count": len(thread_info),
            "threads": thread_info
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error getting thread information: {str(e)}"
        }), 500
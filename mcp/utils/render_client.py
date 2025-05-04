"""
Render API client for the MCP module.

This module provides a client for interacting with the Render API
to manage the RedBarSushiAI staging environment.
"""
import requests
import logging
import time
from typing import Dict, Any, List, Optional

from mcp.config import Config

logger = logging.getLogger(__name__)


class RenderClient:
    """
    Client for interacting with the Render API.
    """

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.RENDER_API_KEY
        self.service_id = config.RENDER_SERVICE_ID
        self.base_url = "https://api.render.com/v1"
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_service(self) -> Dict[str, Any]:
        """
        Get information about the service.

        Returns:
            Service information.
        """
        url = f"{self.base_url}/services/{self.service_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def restart_service(self) -> Dict[str, Any]:
        """
        Restart the service.

        Returns:
            The response from the restart request.
        """
        url = f"{self.base_url}/services/{self.service_id}/restart"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def suspend_service(self) -> Dict[str, Any]:
        """
        Suspend the service.

        Returns:
            The response from the suspend request.
        """
        url = f"{self.base_url}/services/{self.service_id}/suspend"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def resume_service(self) -> Dict[str, Any]:
        """
        Resume the service.

        Returns:
            The response from the resume request.
        """
        url = f"{self.base_url}/services/{self.service_id}/resume"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_service_logs(
        self, limit: int = 100, start_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get service logs.

        Args:
            limit: Maximum number of log entries to return.
            start_time: ISO 8601 timestamp to start from.

        Returns:
            List of log entries.
        """
        url = f"{self.base_url}/services/{self.service_id}/logs"
        params = {"limit": limit}
        if start_time:
            params["startTime"] = start_time

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_deploys(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent deploys.

        Args:
            limit: Maximum number of deploys to return.

        Returns:
            List of deploys.
        """
        url = f"{self.base_url}/services/{self.service_id}/deploys"
        params = {"limit": limit}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def check_service_health(self) -> Dict[str, Any]:
        """
        Check if the service is healthy.

        Returns:
            Health status information.
        """
        try:
            service = self.get_service()
            status = service.get("status", "unknown")
            is_healthy = status == "live"

            result = {
                "success": True,
                "is_healthy": is_healthy,
                "status": status,
                "service_details": service,
            }

            if not is_healthy:
                logger.warning(f"Service is not healthy. Status: {status}")
                # Get recent logs for diagnosis
                logs = self.get_service_logs(limit=20)
                errors = [
                    log for log in logs if log.get("level", "").lower() == "error"
                ]
                result["errors"] = errors

            return result
        except Exception as e:
            logger.error(f"Error checking service health: {e}")
            return {
                "success": False,
                "is_healthy": False,
                "error": str(e),
            }

    def check_and_fix_service_health(self) -> Dict[str, Any]:
        """
        Check service health and attempt to fix any issues.

        Returns:
            Result of the health check and fix.
        """
        # First, check the health
        health = self.check_service_health()
        if health.get("is_healthy", False):
            return {
                "success": True,
                "is_healthy": True,
                "message": "Service is healthy.",
                "actions_taken": [],
            }

        # If not healthy, try to fix
        actions_taken = []
        current_status = health.get("status", "unknown")

        # If the service is crashed, first suspend and then resume
        if current_status in ["crashed", "health_check_failing"]:
            logger.info(f"Service is {current_status}, attempting suspend/resume")
            try:
                self.suspend_service()
                actions_taken.append("suspend")
                time.sleep(5)  # Wait for the suspend to take effect
                self.resume_service()
                actions_taken.append("resume")
                time.sleep(10)  # Wait for the resume to take effect
            except Exception as e:
                logger.error(f"Error during suspend/resume: {e}")
                return {
                    "success": False,
                    "is_healthy": False,
                    "message": f"Failed to suspend/resume service: {e}",
                    "actions_taken": actions_taken,
                }

        # If still not responding or in another state, try a restart
        if current_status not in ["live"]:
            logger.info(f"Service still not healthy, attempting restart")
            try:
                self.restart_service()
                actions_taken.append("restart")
                time.sleep(30)  # Wait for the restart to take effect
            except Exception as e:
                logger.error(f"Error during restart: {e}")
                return {
                    "success": False,
                    "is_healthy": False,
                    "message": f"Failed to restart service: {e}",
                    "actions_taken": actions_taken,
                }

        # Check health again after attempted fixes
        final_health = self.check_service_health()
        is_healthy = final_health.get("is_healthy", False)
        final_status = final_health.get("status", "unknown")

        return {
            "success": is_healthy,
            "is_healthy": is_healthy,
            "initial_status": current_status,
            "final_status": final_status,
            "message": (
                f"Service is now {final_status}."
                if is_healthy
                else f"Service is still not healthy after fixes. Status: {final_status}"
            ),
            "actions_taken": actions_taken,
        }
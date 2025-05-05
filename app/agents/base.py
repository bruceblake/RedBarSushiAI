"""
Base agent classes and utilities for RedBarSushiAI.
This module provides the foundation for all agent implementations.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, Callable
import openai

# Define tool directly since we can't import it
from functools import wraps
def tool(*args, **kwargs):
    """Simple tool decorator for OpenAI tools."""
    if callable(args) and len(args) == 1:
        # @tool directly on a function
        func = args[0]
        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped
    else:
        # @tool(name="...") form
        def decorator(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapped
        return decorator

# Define basic class for Tool
class Tool:
    """Compatibility Tool class."""
    def __init__(self, function=None, parameters=None, description=None):
        self.function = function
        self.parameters = parameters
        self.description = description

# Define other needed classes
class Agent:
    """Compatibility Agent class."""
    pass
    
class Message:
    """Compatibility Message class."""
    pass
    
class Run:
    """Compatibility Run class."""
    pass
    
class Thread:
    """Compatibility Thread class."""
    pass
    
class ToolChoice:
    """Compatibility ToolChoice class."""
    pass

# Create an AgentsClient class
class AgentsClient:
    """Compatibility AgentsClient class."""
    def __init__(self, *args, **kwargs):
        pass
    Message = type('Message', (), {})
    Run = type('Run', (), {})
    Thread = type('Thread', (), {})
    ToolChoice = type('ToolChoice', (), {})

# Avoid circular import
# Will access these items through the module at runtime
agents_sdk = None

logger = logging.getLogger(__name__)

class BaseAgent:
    """Base class for all agents in the system."""
    
    def __init__(
        self,
        name: str,
        instructions: str,
        model: str = "gpt-4.1-mini",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        guardrails: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        agent_id: Optional[str] = None
    ):
        # Import here to avoid circular import
        global agents_sdk
        if agents_sdk is None:
            import app.utils.agents_sdk as agents_sdk
        """
        Initialize a base agent.
        
        Args:
            name: The name of the agent
            instructions: The system instructions for the agent
            model: The model to use (default: gpt-4.1-mini)
            description: Optional description
            metadata: Optional metadata
            guardrails: Optional guardrail settings
            tools: Optional list of tools the agent can use
            agent_id: Optional agent ID if already registered
        """
        self.name = name
        self.instructions = instructions
        self.model = model
        self.description = description or f"{name} Agent for RedBarSushiAI"
        self.metadata = metadata or {"application": "RedBarSushiAI"}
        self.guardrails = guardrails
        self.tools = tools or []
        
        # If agent_id is provided, retrieve the agent; otherwise register it
        self.agent_id = agent_id
        self.agent = None
        
        # For policy enforcement
        self.policy_agent = None
        
        if agents_sdk and agents_sdk.agents_client:
            try:
                if agent_id:
                    self.agent = agents_sdk.agents_client.agents.retrieve(agent_id)
                    logger.info(f"Retrieved agent {name} with ID {agent_id}")
                else:
                    # Register a new agent
                    self.register()
            except Exception as e:
                logger.error(f"Error initializing agent {name}: {str(e)}")
    
    def register(self) -> Optional[Agent]:
        """
        Register the agent with OpenAI if not already registered.
        
        Returns:
            The agent object if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client:
            logger.error("Agents client not available")
            return None
        
        if self.agent:
            return self.agent
        
        try:
            # Create the agent
            self.agent = agents_sdk.agents_client.agents.create(
                name=self.name,
                description=self.description,
                model=self.model,
                instructions=self.instructions,
                tools=self.tools,
                metadata=self.metadata
            )
            
            self.agent_id = self.agent.id
            logger.info(f"Registered agent {self.name} with ID {self.agent_id}")
            return self.agent
        
        except Exception as e:
            logger.error(f"Failed to register agent: {str(e)}")
            return None
    
    def create_thread(self) -> Optional[Thread]:
        """
        Create a new thread for this agent.
        
        Returns:
            The thread object if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client:
            logger.error("Agents client not available")
            return None
        
        try:
            return agents_sdk.agents_client.threads.create()
        except Exception as e:
            logger.error(f"Error creating thread: {str(e)}")
            return None
    
    def add_message(
        self, 
        thread_id: str, 
        content: str, 
        role: str = "user"
    ) -> Optional[Message]:
        """
        Add a message to a thread.
        
        Args:
            thread_id: The thread ID
            content: The message content
            role: The message role (default: user)
            
        Returns:
            The message object if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client:
            logger.error("Agents client not available")
            return None
        
        try:
            return agents_sdk.agents_client.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
        except Exception as e:
            logger.error(f"Error adding message to thread {thread_id}: {str(e)}")
            return None
    
    def run(
        self, 
        thread_id: str, 
        tool_choice: Optional[ToolChoice] = None
    ) -> Optional[Run]:
        """
        Run the agent on a thread.
        
        Args:
            thread_id: The thread ID
            tool_choice: Optional tool choice
            
        Returns:
            The run object if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client or not self.agent_id:
            logger.error("Agents client or agent ID not available")
            return None
        
        try:
            return agents_sdk.agents_client.runs.create(
                thread_id=thread_id,
                agent_id=self.agent_id,
                tool_choice=tool_choice
            )
        except Exception as e:
            logger.error(f"Error running agent on thread {thread_id}: {str(e)}")
            return None
    
    def wait_for_run(self, thread_id: str, run_id: str) -> Optional[Run]:
        """
        Wait for a run to complete.
        
        Args:
            thread_id: The thread ID
            run_id: The run ID
            
        Returns:
            The run object if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client:
            logger.error("Agents client not available")
            return None
        
        try:
            return agents_sdk.agents_client.runs.wait(
                thread_id=thread_id,
                run_id=run_id
            )
        except Exception as e:
            logger.error(f"Error waiting for run {run_id}: {str(e)}")
            return None
    
    def get_response(self, thread_id: str, after_message_id: Optional[str] = None) -> Optional[str]:
        """
        Get the agent's response from a thread.
        
        Args:
            thread_id: The thread ID
            after_message_id: Optional message ID to get messages after
            
        Returns:
            The response text if successful, None otherwise
        """
        if not agents_sdk or not agents_sdk.agents_client:
            logger.error("Agents client not available")
            return None
        
        try:
            # Get messages from the thread
            if after_message_id:
                messages = agents_sdk.agents_client.messages.list(
                    thread_id=thread_id,
                    after=after_message_id
                )
            else:
                messages = agents_sdk.agents_client.messages.list(thread_id=thread_id)
            
            # Get the latest assistant message
            message_list = list(messages)
            for message in message_list:
                if message.role == "assistant":
                    # Extract the text content
                    if message.content:
                        for content_item in message.content:
                            if hasattr(content_item, "text"):
                                return content_item.text.value
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting response from thread {thread_id}: {str(e)}")
            return None
    
    def process_message(self, call_sid: str, message: str) -> Optional[str]:
        """
        Process a message using this agent.
        
        Args:
            call_sid: The Twilio call SID
            message: The message to process
            
        Returns:
            The agent's response if successful, None otherwise
        """
        # Get or create a thread for this call
        thread = agents_sdk.create_or_get_thread(call_sid)
        if not thread:
            logger.error(f"Failed to get or create thread for call {call_sid}")
            return None
        
        thread_id = thread.id
        
        # Add the message to the thread
        user_message = self.add_message(thread_id, message)
        if not user_message:
            logger.error(f"Failed to add message to thread {thread_id}")
            return None
        
        # Run the agent
        start_time = time.time()
        run = self.run(thread_id)
        if not run:
            logger.error(f"Failed to run agent on thread {thread_id}")
            return None
        
        # Wait for the run to complete
        run = self.wait_for_run(thread_id, run.id)
        if not run:
            logger.error(f"Failed to wait for run on thread {thread_id}")
            return None
        
        # Get the agent's response
        response = self.get_response(thread_id, user_message.id)
        
        duration = time.time() - start_time
        logger.info(f"Agent {self.name} processed message in {duration:.2f}s")
        
        return response
    
    def as_tool(self) -> Dict[str, Any]:
        """
        Convert this agent to a tool definition for use by other agents.
        
        Returns:
            A tool definition dict
        """
        return {
            "type": "function",
            "function": {
                "name": f"{self.name.lower().replace(' ', '_')}_agent",
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": f"The query to send to the {self.name} Agent"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    def register_policy_agent(self, policy_agent):
        """
        Register a policy agent (guardrail) to validate actions.
        
        Args:
            policy_agent: The policy agent to register
        """
        self.policy_agent = policy_agent
        logger.info(f"Registered policy agent with {self.name}")
    
    def validate_with_policy(self, validation_type: str, validation_data: Dict[str, Any], call_sid: str) -> Dict[str, Any]:
        """
        Validate data using the registered policy agent.
        
        Args:
            validation_type: The type of validation to perform
            validation_data: The data to validate
            call_sid: The Twilio call SID
            
        Returns:
            Validation result or default validation passed result if no policy agent is registered
        """
        if not self.policy_agent:
            logger.warning(f"No policy agent registered for {self.name}, skipping validation")
            return {"valid": True}
        
        try:
            # Call the policy agent's validate_request method
            result = self.policy_agent.validate_request(call_sid, validation_type, validation_data)
            return result
        except Exception as e:
            logger.error(f"Error validating with policy agent: {str(e)}")
            # Default to valid in case of error to prevent blocking (configurable behavior)
            return {
                "valid": True,
                "warning": f"Validation failed with error: {str(e)}"
            }


class HandoffCapableAgent(BaseAgent):
    """Base class for agents that can handle handoffs to other agents."""
    
    def __init__(self, *args, **kwargs):
        """Initialize a handoff-capable agent."""
        super().__init__(*args, **kwargs)
        self.specialist_agents = {}
    
    def register_specialist(self, name: str, agent: BaseAgent):
        """
        Register a specialist agent that this agent can call as a tool.
        
        Args:
            name: The name of the specialist
            agent: The specialist agent
        """
        self.specialist_agents[name] = agent
        
        # Add the specialist agent as a tool
        tool_def = agent.as_tool()
        self.tools.append(tool_def)
    
    def call_specialist(
        self, 
        specialist_name: str, 
        query: str, 
        call_sid: str
    ) -> Optional[str]:
        """
        Call a specialist agent to handle a query.
        
        Args:
            specialist_name: The name of the specialist
            query: The query to send to the specialist
            call_sid: The Twilio call SID
            
        Returns:
            The specialist's response if successful, None otherwise
        """
        specialist = self.specialist_agents.get(specialist_name)
        if not specialist:
            logger.error(f"Specialist {specialist_name} not registered")
            return None
        
        return specialist.process_message(call_sid, query)
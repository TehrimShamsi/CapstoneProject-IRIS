# backend/app/protocol/a2a_messages.py
"""
A2A (Agent-to-Agent) Protocol Implementation
Message-based communication for multi-agent orchestration
"""

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# ============================================
# Message Types
# ============================================

class A2AMessage(BaseModel):
    """Base A2A protocol message"""
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agents: List[str]
    msg_type: Literal["task", "result", "status", "request", "error"]
    payload: Dict[str, Any]
    trace_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    priority: int = Field(default=0, ge=0, le=10)  # 0=low, 10=urgent


class TaskMessage(A2AMessage):
    """Task assignment message"""
    msg_type: Literal["task"] = "task"
    task_name: str
    parameters: Dict[str, Any]


class ResultMessage(A2AMessage):
    """Task result message"""
    msg_type: Literal["result"] = "result"
    task_id: str
    status: Literal["success", "failed"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StatusMessage(A2AMessage):
    """Agent status update"""
    msg_type: Literal["status"] = "status"
    agent_status: Literal["idle", "busy", "processing", "error"]
    current_task: Optional[str] = None
    progress: Optional[float] = None  # 0.0 to 1.0


class RequestMessage(A2AMessage):
    """Request for data/action"""
    msg_type: Literal["request"] = "request"
    request_type: str
    requested_data: Dict[str, Any]


class ErrorMessage(A2AMessage):
    """Error notification"""
    msg_type: Literal["error"] = "error"
    error_code: str
    error_message: str
    stack_trace: Optional[str] = None


# ============================================
# Message Router
# ============================================

class MessageRouter:
    """Routes messages between agents"""
    
    def __init__(self):
        self.message_queue: List[A2AMessage] = []
        self.agent_registry: Dict[str, Any] = {}
        self.message_history: List[A2AMessage] = []
    
    def register_agent(self, agent_name: str, agent_instance: Any):
        """Register an agent for message routing"""
        self.agent_registry[agent_name] = agent_instance
    
    def send_message(self, message: A2AMessage):
        """Send message to target agents"""
        self.message_queue.append(message)
        self.message_history.append(message)
        
        # Route to target agents
        for target in message.to_agents:
            if target in self.agent_registry:
                agent = self.agent_registry[target]
                if hasattr(agent, 'receive_message'):
                    agent.receive_message(message)
    
    def broadcast(self, message: A2AMessage):
        """Broadcast message to all registered agents"""
        message.to_agents = list(self.agent_registry.keys())
        self.send_message(message)
    
    def get_messages_by_trace(self, trace_id: str) -> List[A2AMessage]:
        """Get all messages for a specific trace"""
        return [m for m in self.message_history if m.trace_id == trace_id]
    
    def clear_queue(self):
        """Clear message queue"""
        self.message_queue.clear()


# ============================================
# Agent Base Class with A2A Support
# ============================================

class A2AAgent:
    """Base class for agents supporting A2A protocol"""
    
    def __init__(self, agent_name: str, router: MessageRouter):
        self.agent_name = agent_name
        self.router = router
        self.status = "idle"
        self.current_task = None
        
        # Register with router
        router.register_agent(agent_name, self)
    
    def send_task(self, to_agent: str, task_name: str, parameters: Dict[str, Any], trace_id: str):
        """Send task to another agent"""
        message = TaskMessage(
            from_agent=self.agent_name,
            to_agents=[to_agent],
            task_name=task_name,
            parameters=parameters,
            payload={"task_name": task_name, "parameters": parameters},
            trace_id=trace_id
        )
        self.router.send_message(message)
    
    def send_result(self, to_agent: str, task_id: str, result: Dict[str, Any], trace_id: str):
        """Send task result"""
        message = ResultMessage(
            from_agent=self.agent_name,
            to_agents=[to_agent],
            task_id=task_id,
            status="success",
            result=result,
            payload={"task_id": task_id, "result": result},
            trace_id=trace_id
        )
        self.router.send_message(message)
    
    def send_status(self, status: str, progress: Optional[float] = None, trace_id: str = "system"):
        """Send status update"""
        self.status = status
        message = StatusMessage(
            from_agent=self.agent_name,
            to_agents=["Orchestrator"],
            agent_status=status,
            current_task=self.current_task,
            progress=progress,
            payload={"status": status, "progress": progress},
            trace_id=trace_id
        )
        self.router.send_message(message)
    
    def send_error(self, error_code: str, error_message: str, trace_id: str):
        """Send error notification"""
        message = ErrorMessage(
            from_agent=self.agent_name,
            to_agents=["Orchestrator"],
            error_code=error_code,
            error_message=error_message,
            payload={"error_code": error_code, "error_message": error_message},
            trace_id=trace_id
        )
        self.router.send_message(message)
    
    def receive_message(self, message: A2AMessage):
        """Handle incoming message (override in subclasses)"""
        if message.msg_type == "task":
            self.handle_task(message)
        elif message.msg_type == "request":
            self.handle_request(message)
    
    def handle_task(self, message: A2AMessage):
        """Handle task message (override in subclasses)"""
        pass
    
    def handle_request(self, message: A2AMessage):
        """Handle request message (override in subclasses)"""
        pass


# ============================================
# Convenience Functions
# ============================================

def create_trace_id() -> str:
    """Create new trace ID for request tracking"""
    return str(uuid.uuid4())[:8]


def create_task_message(from_agent: str, to_agent: str, task_name: str, 
                        parameters: Dict[str, Any], trace_id: str) -> TaskMessage:
    """Helper to create task message"""
    return TaskMessage(
        from_agent=from_agent,
        to_agents=[to_agent],
        task_name=task_name,
        parameters=parameters,
        payload={"task_name": task_name, "parameters": parameters},
        trace_id=trace_id
    )
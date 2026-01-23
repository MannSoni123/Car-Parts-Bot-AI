"""
Lead management and auto-assignment service.
Handles lead assignment to sales agents.
"""
from typing import Any
from flask import current_app
from ..extensions import db
from ..models import Lead


class LeadService:
    """Service for managing leads and auto-assignment to sales agents."""
    

    def assign_lead(self, lead: Lead) -> str | None:
        """
        Auto-assign a lead to a sales agent using round-robin or availability.
        Returns assigned agent name/ID.
        """
        # Get list of available agents from config (can be enhanced with DB later)
        agents = current_app.config.get("SALES_AGENTS", ["agent1", "agent2", "agent3"])

        if not agents:
            return None

        # Simple round-robin: get count of leads assigned to each agent
        agent_counts = {}
        for agent in agents:
            count = db.session.query(Lead).filter_by(assigned_agent=agent).count()
            agent_counts[agent] = count

        # Assign to agent with least leads
        assigned_agent = min(agent_counts, key=agent_counts.get)
        lead.assigned_agent = assigned_agent
        lead.status = "assigned"
        db.session.commit()

        return assigned_agent

    def create_lead(
        self, whatsapp_user_id: str, query_text: str, intent: str | None = None
    ) -> Lead:
        """Create a new lead from WhatsApp message."""
        
        lead = Lead(
            whatsapp_user_id=whatsapp_user_id,
            query_text=query_text,
            intent=intent,
            status="new",
        )
        
        db.session.add(lead)
        print("Creating lead...")
        db.session.commit()
        print("Lead created with ID:", lead.id)
        # Auto-assign
        self.assign_lead(lead)

        return lead

lead_service = LeadService()
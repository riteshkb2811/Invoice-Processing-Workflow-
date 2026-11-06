from langchain_core.prompts import ChatPromptTemplate

from app.database.models import InvoiceExtraction, PolicyAudit
from app.services.llm_service import llm

prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an enterprise invoice compliance auditor.
Audit the invoice strictly against the provided company policies.

Guidelines:
1. Do not invent company policies; base your audit only on the provided text.
2. If mandatory invoice details are missing, report them as policy issues.
3. Identify policy violations clearly with explanation and severity (Low, Medium, High).
4. Set compliant to true only if all applicable policies are met and no violations are found.
5. Provide actionable recommendations if violations or missing details exist.
6. Do not approve invoices yourself; only assess policy compliance.""",
    ),
    (
        "human",
        """Invoice Information:
{invoice}

Company Policies:
{policies}

Perform the policy audit.""",
    ),
])


def audit_invoice(
    invoice: InvoiceExtraction,
    policy_context: str,
) -> PolicyAudit:
    if not policy_context or not policy_context.strip():
        return PolicyAudit(
            compliant=True,
            violations=[],
            recommendations=["No specific policy context retrieved for this invoice category."],
        )

    invoice_json = (
        invoice.model_dump_json()
        if hasattr(invoice, "model_dump_json")
        else str(invoice)
    )

    try:
        structured_llm = llm.with_structured_output(
            PolicyAudit,
            method="json_schema",
            strict=True,
        )
        chain = prompt | structured_llm
        return chain.invoke({
            "invoice": invoice_json,
            "policies": policy_context,
        })
    except Exception as error:
        return PolicyAudit(
            compliant=False,
            violations=[
                {
                    "policy_name": "Audit Service",
                    "issue": "Policy audit execution encountered an error",
                    "explanation": str(error),
                    "severity": "Medium",
                }
            ],
            recommendations=["Perform manual compliance review."],
        )

import type { ApprovalPayload } from "../types/jarvis";

type ApprovalPanelProps = {
  approval: ApprovalPayload;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
};

export function ApprovalPanel({ approval, onApprove, onReject }: ApprovalPanelProps) {
  return (
    <section className="panel-surface approval-panel">
      <div className="panel-heading">
        <span className="eyebrow">Approval Gate</span>
        <h3>{approval.action_summary || "Supervised action pending"}</h3>
      </div>
      <div className="approval-grid">
        <div>
          <label>Why</label>
          <p>{approval.reason || "This action crosses the supervised execution boundary."}</p>
        </div>
        <div>
          <label>Risk</label>
          <p>{approval.risk_level} / {approval.permission_level}</p>
        </div>
        <div>
          <label>Expected Result</label>
          <p>{approval.expected_result || "Review before execution."}</p>
        </div>
        <div>
          <label>Approval ID</label>
          <p>{approval.approval_id}</p>
        </div>
      </div>
      <div className="approval-actions">
        <button className="action-button approve" onClick={() => onApprove(approval.approval_id)} type="button">
          Approve
        </button>
        <button className="action-button reject" onClick={() => onReject(approval.approval_id)} type="button">
          Reject
        </button>
      </div>
    </section>
  );
}
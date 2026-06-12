import { useEffect, useState, useTransition } from "react";

import { JarvisCockpit } from "./components/JarvisCockpit";
import { approveApproval, connectBridgeEvents, loadBridgeState, rejectApproval, sendJarvisCommand } from "./bridge/pythonBridge";
import {
  applyBridgeEvent,
  applySocketConnected,
  applyApprovalResolution,
  applyBridgeResponse,
  applyPendingCommand,
  createInitialJarvisUiState,
  hydrateBridgeState,
  type JarvisUiState,
} from "./state/jarvisState";

export default function App() {
  const [uiState, setUiState] = useState<JarvisUiState>(createInitialJarvisUiState());
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    let active = true;
    loadBridgeState()
      .then((state) => {
        if (!active) {
          return;
        }
        setUiState((current) => hydrateBridgeState(current, state));
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        setUiState((current) => ({
          ...current,
          activeState: "disconnected",
          backendDetail: error instanceof Error ? error.message : String(error),
          errorMessage: error instanceof Error ? error.message : String(error),
        }));
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return connectBridgeEvents({
      onOpen: () => {
        setUiState((current) => applySocketConnected(current, true));
      },
      onClose: () => {
        setUiState((current) => applySocketConnected(current, false));
      },
      onError: (message) => {
        setUiState((current) => ({ ...current, errorMessage: message }));
      },
      onEvent: (event) => {
        setUiState((current) => applyBridgeEvent(current, event));
      },
    });
  }, []);

  const handleSendCommand = async (message: string) => {
    const normalized = message.trim();
    if (!normalized) {
      return;
    }
    setUiState((current) => applyPendingCommand(current, normalized));
    try {
      const response = await sendJarvisCommand(normalized, uiState.conversationId);
      startTransition(() => {
        setUiState((current) => applyBridgeResponse(current, response));
      });
    } catch (error: unknown) {
      setUiState((current) => ({
        ...current,
        activeState: "error",
        requestPending: false,
        errorMessage: error instanceof Error ? error.message : String(error),
      }));
    }
  };

  const handleApprove = async (approvalId: string) => {
    try {
      const result = await approveApproval(approvalId);
      setUiState((current) => applyApprovalResolution(current, "approve", result.message));
    } catch (error: unknown) {
      setUiState((current) => ({
        ...current,
        activeState: "error",
        errorMessage: error instanceof Error ? error.message : String(error),
      }));
    }
  };

  const handleReject = async (approvalId: string) => {
    try {
      const result = await rejectApproval(approvalId);
      setUiState((current) => applyApprovalResolution(current, "reject", result.message));
    } catch (error: unknown) {
      setUiState((current) => ({
        ...current,
        activeState: "error",
        errorMessage: error instanceof Error ? error.message : String(error),
      }));
    }
  };

  return (
    <JarvisCockpit
      uiState={uiState}
      isPending={isPending}
      onSendCommand={handleSendCommand}
      onApprove={handleApprove}
      onReject={handleReject}
    />
  );
}
"use client";

import { Component, type ReactNode } from "react";
import FaultyTerminal from "./FaultyTerminal";

interface State { crashed: boolean }

class FaultyTerminalBoundary extends Component<{ children?: ReactNode }, State> {
  state: State = { crashed: false };
  static getDerivedStateFromError() { return { crashed: true }; }
  render() { return this.state.crashed ? null : this.props.children; }
}

export default function FaultyTerminalSafe(props: React.ComponentProps<typeof FaultyTerminal>) {
  return (
    <FaultyTerminalBoundary>
      <FaultyTerminal {...props} />
    </FaultyTerminalBoundary>
  );
}

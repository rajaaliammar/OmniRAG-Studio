"use client";

import { TriangleAlert } from "lucide-react";
import { Component, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type ErrorBoundaryProps = {
  children: ReactNode;
  title?: string;
};

type ErrorBoundaryState = {
  hasError: boolean;
};

/** Keep one dashboard panel from crashing the entire page. */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  override componentDidCatch(error: Error): void {
    console.error(error);
  }

  private handleRetry = () => {
    this.setState({ hasError: false });
  };

  override render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <Card className="flex min-h-[320px] flex-col justify-center">
        <CardHeader>
          <CardTitle>{this.props.title ?? "Panel failed"}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 text-center text-sm text-muted-foreground">
          <TriangleAlert className="size-8 text-destructive" />
          <p>
            Something went wrong while rendering this panel. Retry after the
            current state is reset.
          </p>
          <Button type="button" variant="outline" onClick={this.handleRetry}>
            Retry panel
          </Button>
        </CardContent>
      </Card>
    );
  }
}

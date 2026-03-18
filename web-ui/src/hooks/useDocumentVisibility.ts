"use client";

import { useEffect, useState } from "react";

function getInitialVisibility() {
  if (typeof document === "undefined") {
    return true;
  }
  return document.visibilityState !== "hidden";
}

export function useDocumentVisibility() {
  const [isVisible, setIsVisible] = useState(getInitialVisibility);

  useEffect(() => {
    function handleVisibilityChange() {
      setIsVisible(document.visibilityState !== "hidden");
    }

    handleVisibilityChange();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  return isVisible;
}

"use client";

import { useEffect, useState } from "react";

/**
 * Load a value for `key`, treating anything loaded for a different key as absent.
 *
 * The obvious shape — `setValue(null)` at the top of the effect, then fetch — trips
 * react-hooks/set-state-in-effect, and the rule is right: a synchronous setState inside
 * an effect renders twice for every change. Carrying the key alongside the value makes
 * staleness derivable instead of something you have to clear.
 */
export function useLoaded<T>(key: string | null, load: (key: string) => Promise<T>) {
  const [held, setHeld] = useState<{ key: string; value: T | null; failed: boolean } | null>(null);

  useEffect(() => {
    if (key == null) return;
    let live = true;
    load(key).then(
      (value) => { if (live) setHeld({ key, value, failed: false }); },
      () => { if (live) setHeld({ key, value: null, failed: true }); },
    );
    return () => { live = false; };
  }, [key, load]);

  const fresh = held !== null && held.key === key;
  return {
    value: fresh ? held.value : null,
    failed: fresh ? held.failed : false,
    loading: key !== null && !fresh,
  };
}

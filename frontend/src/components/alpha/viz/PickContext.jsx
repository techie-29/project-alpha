import { createContext, useContext } from "react";

/** Lets a chart bar open the findings about that group. `pick(name)` returns a function to call on click, or null when no finding mentions it. */
export const PickContext = createContext(() => null);
export const usePick = () => useContext(PickContext);

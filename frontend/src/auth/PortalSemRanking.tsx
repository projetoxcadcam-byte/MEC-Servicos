import type { ReactNode } from "react";
import "./PortalSemRanking.css";

// Os layouts locais são preservados. A navegação destes portais não apresenta
// links de comparação entre fornecedores. A autorização é feita pela API.
export default function PortalSemRanking({ children }: { children: ReactNode }) {
  return <div className="mec-portal-sem-ranking">{children}</div>;
}

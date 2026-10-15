import { lazy, Suspense } from "react";
import type { PerfilTutorial } from "./dadosTutorial";

const TutorialPage = lazy(() => import("./TutorialPage"));

export default function TutorialEntrada({ perfil }: { perfil: PerfilTutorial }) {
  return <Suspense fallback={<section className="t66"><p role="status">Abrindo o tutorial…</p></section>}>
    <TutorialPage perfil={perfil} />
  </Suspense>;
}

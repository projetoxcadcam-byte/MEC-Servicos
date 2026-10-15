import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { limparAcessoLocal, requisitarAcesso, type UsuarioServidor } from "../../services/acesso";
import "./ContaAcessoPage.css";

type Conta = UsuarioServidor & { ativo: boolean };
export default function ContaAcessoPage() {
  const { user, logout } = useAuth();
  const [atual, setAtual] = useState(""); const [nova, setNova] = useState(""); const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState(""); const [aviso, setAviso] = useState(""); const [ocupado, setOcupado] = useState(false);
  const [contas, setContas] = useState<Conta[]>([]); const [revisao, setRevisao] = useState(0);
  const [cadastro, setCadastro] = useState({ nome: "", email: "", perfil: "cliente", empresa: "", senha: "" });
  const [alvo, setAlvo] = useState<number | null>(null); const [senhaAlvo, setSenhaAlvo] = useState("");
  const trava = useRef(false); const montada = useRef(true);
  useEffect(() => { montada.current = true; return () => { montada.current = false; }; }, []);
  useEffect(() => {
    let vigente = true;
    if (user?.role !== "admin" || user.deve_alterar_senha) return;
    void requisitarAcesso<Conta[]>("/usuarios").then((itens) => { if (vigente) setContas(itens); })
      .catch((falha: unknown) => { if (vigente) setErro(falha instanceof Error ? falha.message : "Não foi possível carregar as contas."); });
    return () => { vigente = false; };
  }, [user?.usuario_id, user?.role, user?.deve_alterar_senha, revisao]);
  if (!user) return <Navigate to="/login" replace />;
  async function executar(acao: () => Promise<void>) {
    if (trava.current) return;
    trava.current = true; setOcupado(true); setErro(""); setAviso("");
    try { await acao(); }
    catch (falha) { if (montada.current) setErro(falha instanceof Error ? falha.message : "Não foi possível concluir a operação."); }
    finally { trava.current = false; if (montada.current) setOcupado(false); }
  }
  function mudarSenha(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (nova !== confirmacao) { setErro("A confirmação deve ser igual à nova senha."); return; }
    void executar(async () => {
      await requisitarAcesso("/alterar-senha", { senha_atual: atual, nova_senha: nova });
      setAtual(""); setNova(""); setConfirmacao("");
      limparAcessoLocal();
    });
  }
  function criar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    void executar(async () => {
      await requisitarAcesso("/usuarios", { nome: cadastro.nome, email: cadastro.email, perfil: cadastro.perfil,
        empresa_id: cadastro.perfil === "admin" ? null : Number(cadastro.empresa), senha: cadastro.senha });
      setCadastro({ nome: "", email: "", perfil: "cliente", empresa: "", senha: "" });
      setAviso("Conta criada. Entregue a senha inicial ao titular; ele deverá alterá-la no primeiro acesso."); setRevisao((v) => v + 1);
    });
  }
  function redefinir(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault(); if (alvo === null) return;
    void executar(async () => {
      await requisitarAcesso(`/usuarios/${alvo}/redefinir-senha`, { nova_senha: senhaAlvo });
      const propria = alvo === user?.usuario_id; setSenhaAlvo(""); setAlvo(null);
      if (propria) limparAcessoLocal();
      else { setAviso("Senha inicial redefinida e sessões anteriores encerradas. Entregue-a ao titular."); setRevisao((v) => v + 1); }
    });
  }
  return <main className="a30-page"><header><div><p>MEC SERVIÇOS</p><h1>Minha conta</h1><span>{user.nome} · {user.email}</span></div><nav>
    {!user.deve_alterar_senha && <Link to={`/${user.role}`}>Voltar ao portal</Link>}<button disabled={ocupado} onClick={() => void logout()}>Sair</button></nav></header>
    {user.deve_alterar_senha && <p className="a30-notice">Altere a senha inicial para acessar o portal. Após salvar, entre novamente com a nova senha.</p>}
    {erro && <p className="a30-error" role="alert">{erro}</p>}{aviso && <p className="a30-notice" role="status">{aviso}</p>}
    <section><h2>Alterar minha senha</h2><p>Use de 12 a 128 caracteres. A alteração encerra todas as sessões desta conta.</p>
      <form onSubmit={mudarSenha}><fieldset disabled={ocupado}>
        <label>Senha atual<input type="password" autoComplete="current-password" value={atual} onChange={(e) => setAtual(e.target.value)} maxLength={128} required /></label>
        <label>Nova senha<input type="password" autoComplete="new-password" value={nova} onChange={(e) => setNova(e.target.value)} minLength={12} maxLength={128} required /></label>
        <label>Confirmar nova senha<input type="password" autoComplete="new-password" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} minLength={12} maxLength={128} required /></label>
        <button type="submit">{ocupado ? "Aguarde…" : "Salvar nova senha"}</button>
      </fieldset></form></section>
    {user.role === "admin" && !user.deve_alterar_senha && <>
      <section><h2>Criar acesso</h2><form onSubmit={criar}><fieldset disabled={ocupado}>
        <label>Nome do titular<input value={cadastro.nome} onChange={(e) => setCadastro({ ...cadastro, nome: e.target.value })} maxLength={120} required /></label>
        <label>E-mail de acesso<input type="email" value={cadastro.email} onChange={(e) => setCadastro({ ...cadastro, email: e.target.value })} maxLength={254} required /></label>
        <label>Perfil<select value={cadastro.perfil} onChange={(e) => setCadastro({ ...cadastro, perfil: e.target.value, empresa: "" })}><option value="cliente">Cliente</option><option value="fornecedor">Fornecedor</option><option value="admin">Administrador</option></select></label>
        {cadastro.perfil !== "admin" && <label>ID da empresa já cadastrada<input type="number" min={1} step={1} value={cadastro.empresa} onChange={(e) => setCadastro({ ...cadastro, empresa: e.target.value })} required /></label>}
        <label>Senha inicial<input type="password" autoComplete="new-password" value={cadastro.senha} onChange={(e) => setCadastro({ ...cadastro, senha: e.target.value })} minLength={12} maxLength={128} required /></label>
        <button type="submit">Criar conta</button></fieldset></form></section>
      <section><h2>Acessos cadastrados</h2><div className="a30-table"><table><thead><tr><th>Titular</th><th>Perfil / empresa</th><th>Situação</th><th>Ações</th></tr></thead><tbody>{contas.map((conta) => <tr key={conta.usuario_id}>
        <td>{conta.nome}<small>{conta.email}</small></td><td>{conta.role}<small>{conta.empresa_id ? `Empresa #${conta.empresa_id}` : "Administração"}</small></td>
        <td>{conta.ativo ? "Ativa" : "Desativada"}{conta.deve_alterar_senha && <small>Senha inicial</small>}</td><td>
          <button disabled={ocupado || conta.usuario_id === user.usuario_id} onClick={() => void executar(async () => {
            await requisitarAcesso(`/usuarios/${conta.usuario_id}/ativo`, { ativo: !conta.ativo }, "PATCH"); setRevisao((v) => v + 1);
          })}>{conta.ativo ? "Desativar" : "Ativar"}</button>
          <button disabled={ocupado} onClick={() => { setAlvo(conta.usuario_id); setSenhaAlvo(""); }}>Redefinir senha</button>
        </td></tr>)}</tbody></table></div>
        {alvo !== null && <form onSubmit={redefinir}><fieldset disabled={ocupado}><p>Redefinir senha do titular #{alvo}. As sessões dele serão encerradas.</p>
          <label>Nova senha inicial<input type="password" autoComplete="new-password" value={senhaAlvo} onChange={(e) => setSenhaAlvo(e.target.value)} minLength={12} maxLength={128} required /></label>
          <button type="submit">Confirmar redefinição</button><button type="button" onClick={() => { setAlvo(null); setSenhaAlvo(""); }}>Cancelar</button>
        </fieldset></form>}
      </section></>}
  </main>;
}

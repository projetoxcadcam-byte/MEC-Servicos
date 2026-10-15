import axios, { type AxiosRequestConfig } from "axios";
import { limparAcessoLocal, obterCsrf } from "./acesso";

export const api = axios.create({ baseURL: "/api/v1", withCredentials: true });
function propriaApi(config: AxiosRequestConfig) {
  const endereco = new URL(api.getUri(config), window.location.href);
  return endereco.origin === window.location.origin && /^\/api\/v1(?:\/|$)/.test(endereco.pathname);
}
api.interceptors.request.use((config) => {
  const metodo = (config.method ?? "get").toUpperCase();
  if (propriaApi(config) && !["GET", "HEAD", "OPTIONS"].includes(metodo) && obterCsrf()) config.headers.set("X-MEC-CSRF", obterCsrf());
  return config;
});
api.interceptors.response.use((resposta) => resposta, (erro) => {
  if (erro?.response?.status === 401 && erro?.config && propriaApi(erro.config)) limparAcessoLocal();
  return Promise.reject(erro);
});

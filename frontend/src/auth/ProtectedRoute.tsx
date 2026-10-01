import { Navigate, useLocation } from "react-router-dom";
import { useAuth, type UserRole } from "./AuthContext";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  role: UserRole;
  children: ReactNode;
}

function homeForRole(role: UserRole) {
  switch (role) {
    case "admin":
      return "/admin";
    case "fornecedor":
      return "/fornecedor";
    case "cliente":
      return "/cliente";
  }
}

export default function ProtectedRoute({
  role,
  children,
}: ProtectedRouteProps) {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  if (user.role !== role) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }

  return <>{children}</>;
}

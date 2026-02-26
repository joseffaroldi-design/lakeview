import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Lock, ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Login = () => {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await axios.post(
        `${API}/auth/login`, 
        { password }, 
        { 
          withCredentials: true,
          headers: { 'Content-Type': 'application/json' }
        }
      );
      if (response.data.token) {
        localStorage.setItem("admin_token", response.data.token);
        navigate("/dashboard");
      }
    } catch (err) {
      console.error("Login error:", err);
      setError("Invalid password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Link to="/" className="inline-flex items-center text-gold hover:text-gold/80 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Website
        </Link>

        <Card className="bg-cream border-2 border-gold/30">
          <CardHeader className="text-center pb-2">
            <div className="w-16 h-16 mx-auto mb-4 bg-navy rounded-full flex items-center justify-center">
              <Lock className="w-8 h-8 text-gold" />
            </div>
            <CardTitle className="font-serif text-2xl text-navy">Admin Login</CardTitle>
            <p className="font-sans text-sm text-muted-foreground mt-2">
              Enter your password to access the dashboard
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="border-navy/20 text-center text-lg py-6"
                  data-testid="login-password-input"
                  autoFocus
                />
              </div>
              
              {error && (
                <p className="text-destructive text-sm text-center" data-testid="login-error">
                  {error}
                </p>
              )}
              
              <Button
                type="submit"
                disabled={loading || !password}
                className="w-full bg-navy text-cream hover:bg-navy/90 py-6"
                data-testid="login-submit-btn"
              >
                {loading ? "Logging in..." : "Access Dashboard"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-cream/50 text-sm mt-6 font-sans">
          Lakeview Burgers & Seafood Admin
        </p>
      </div>
    </div>
  );
};

export default Login;

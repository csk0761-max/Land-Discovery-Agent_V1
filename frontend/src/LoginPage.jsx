import React, { useState } from 'react';
import { supabase } from './supabaseClient';
import { useNavigate } from 'react-router-dom';
import { Lock, Mail, Loader } from 'lucide-react';
import styled from 'styled-components';

const cinematicVista = `
  @keyframes droneGlide {
    0% { transform: scale(1) translate(0, 0); }
    100% { transform: scale(1.15) translate(-1%, -1%); }
  }
  @keyframes crossFade {
    0%, 33% { opacity: 1; }
    43%, 100% { opacity: 0; }
  }
`;

const LoginContainer = styled.div`
  min-height: 100vh;
  width: 100vw;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  font-family: 'Inter', sans-serif;
  color: #1e293b;
  background-color: #0f172a;
  ${cinematicVista}
`;

const CinematicBackground = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  background-image: url('https://images.unsplash.com/photo-1509391366360-fe5bb58583bb?auto=format&fit=crop&q=90&w=2400');
  background-size: cover;
  background-position: center;
  animation: droneGlide 40s ease-in-out infinite alternate;
`;

const VideoOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at center, rgba(15, 23, 42, 0.4), rgba(15, 23, 42, 0.85));
  z-index: 1;
`;

const LoginCard = styled.div`
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(25px);
  padding: 40px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.5);
  width: 100%;
  max-width: 400px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
  position: relative;
  z-index: 10;
`;

const Title = styled.h1`
  font-size: 24px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 8px;
  background: linear-gradient(to right, #60a5fa, #a855f7);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
`;

const Subtitle = styled.p`
  text-align: center;
  color: #64748b;
  font-size: 14px;
  margin-bottom: 32px;
`;

const InputGroup = styled.div`
  margin-bottom: 20px;
  position: relative;
`;

const Label = styled.label`
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
`;

const InputWrapper = styled.div`
  position: relative;
  display: flex;
  align-items: center;
`;

const IconWrapper = styled.div`
  position: absolute;
  left: 12px;
  color: #64748b;
`;

const Input = styled.input`
  width: 100%;
  background: rgba(248, 250, 252, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 12px;
  padding: 12px 12px 12px 40px;
  color: #1e293b;
  font-size: 14px;
  transition: all 0.2s;

  &:focus {
    outline: none;
    border-color: #3b82f6;
    background: white;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
  }

  &::placeholder {
    color: #94a3b8;
  }
`;

const Button = styled.button`
  width: 100%;
  background: linear-gradient(to right, #3b82f6, #8b5cf6);
  color: white;
  border: none;
  border-radius: 12px;
  padding: 14px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
  }

  &:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
`;

const ErrorMsg = styled.div`
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #dc2626;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 20px;
  text-align: center;
`;

const LoginPage = () => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const navigate = useNavigate();

  const handleAuth = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        setMessage("Check your email for the confirmation link!");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        navigate('/');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <LoginContainer>
      <CinematicBackground />
      <VideoOverlay />
      <LoginCard>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          <img src="/auxilium-logo.svg" alt="Auxilium" style={{ height: '64px', width: 'auto' }} />
        </div>
        <Title>Auxilium V1</Title>
        <Subtitle>Land Discovery Intelligence Platform</Subtitle>

        {error && <ErrorMsg>{error}</ErrorMsg>}
        {message && (
          <div style={{ 
            background: 'rgba(34, 197, 94, 0.1)', 
            border: '1px solid rgba(34, 197, 94, 0.2)', 
            color: '#4ade80', 
            padding: '12px', 
            borderRadius: '8px', 
            fontSize: '13px', 
            marginBottom: '20px', 
            textAlign: 'center' 
          }}>
            {message}
          </div>
        )}

        <form onSubmit={handleAuth}>
          <InputGroup>
            <Label>Email Address</Label>
            <InputWrapper>
              <IconWrapper><Mail size={18} /></IconWrapper>
              <Input 
                type="email" 
                placeholder="name@company.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </InputWrapper>
          </InputGroup>

          <InputGroup>
            <Label>Password</Label>
            <InputWrapper>
              <IconWrapper><Lock size={18} /></IconWrapper>
              <Input 
                type="password" 
                placeholder="••••••••" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </InputWrapper>
          </InputGroup>

          <Button type="submit" disabled={loading}>
            {loading ? <Loader className="animate-spin" size={20} /> : (isSignUp ? 'Create Account' : 'Sign In')}
          </Button>

          <div style={{ textAlign: 'center', marginTop: '20px' }}>
            <button 
              type="button" 
              onClick={() => setIsSignUp(!isSignUp)}
              style={{ 
                background: 'none', 
                border: 'none', 
                color: '#2563eb', 
                fontSize: '13px', 
                cursor: 'pointer',
                textDecoration: 'underline',
                fontWeight: '600'
              }}
            >
              {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
            </button>
          </div>
        </form>
      </LoginCard>
    </LoginContainer>
  );
};

export default LoginPage;

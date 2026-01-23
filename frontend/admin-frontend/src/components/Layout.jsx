import { Sidebar } from './Sidebar';
import { Header } from './Header';

export function Layout({ children, onLogout }) {
    return (
        <div className="min-h-screen bg-gray-50 font-sans">
            <Sidebar onLogout={onLogout} />
            <div className="pl-64">
                <Header />
                <main className="p-8">
                    {children}
                </main>
            </div>
        </div>
    );
}

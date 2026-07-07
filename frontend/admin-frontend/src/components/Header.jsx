import { Crown, User } from 'lucide-react';

export function Header({ userRole }) {
    const isSuperAdmin = userRole === 'super_admin';

    return (
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
            <div className="flex items-center gap-4 w-96">
                {/* Search removed as per user request */}
            </div>

            <div className="flex items-center gap-4">
                {/* Notification bell removed */}
                <div className="flex items-center gap-3 pl-4 border-l border-gray-200">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-medium ${isSuperAdmin ? 'bg-amber-100 text-amber-600 shadow-sm' : 'bg-blue-100 text-blue-700'}`}>
                        {isSuperAdmin ? <Crown className="w-4 h-4" /> : <User className="w-4 h-4" />}
                    </div>
                    <div className="hidden md:block">
                        <p className="text-sm font-medium text-gray-700">CarBot System</p>
                        <p className="text-xs flex items-center gap-1 mt-0.5 text-gray-500 font-medium">
                            {isSuperAdmin ? 'Super Admin' : 'Admin'}
                            {isSuperAdmin && <Crown className="w-4 h-4 text-yellow-500 fill-yellow-400 drop-shadow-md ml-0.5 animate-pulse" />}
                        </p>
                    </div>
                </div>
            </div>
        </header>
    );
}

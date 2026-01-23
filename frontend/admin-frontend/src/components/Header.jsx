import { Bell, Search } from 'lucide-react';

export function Header() {
    return (
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 sticky top-0 z-10">
            <div className="flex items-center gap-4 w-96">
                {/* Search placeholder for future */}
                <div className="relative w-full hidden md:block">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                        type="text"
                        placeholder="Search..."
                        className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all"
                    />
                </div>
            </div>

            <div className="flex items-center gap-4">
                <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors relative">
                    <Bell className="w-5 h-5" />
                    <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
                </button>
                <div className="flex items-center gap-3 pl-4 border-l border-gray-200">
                    <div className="w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-medium text-sm">
                        AD
                    </div>
                    <div className="hidden md:block">
                        <p className="text-sm font-medium text-gray-700">Admin User</p>
                        <p className="text-xs text-gray-500">Super Admin</p>
                    </div>
                </div>
            </div>
        </header>
    );
}

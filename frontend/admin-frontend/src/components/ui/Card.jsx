import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs) {
    return twMerge(clsx(inputs));
}

export function Card({ className, children, ...props }) {
    return (
        <div
            className={cn('bg-white rounded-xl shadow-sm border border-gray-100', className)}
            {...props}
        >
            {children}
        </div>
    );
}

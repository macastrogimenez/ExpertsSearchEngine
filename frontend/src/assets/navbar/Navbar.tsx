function Navbar (){
    return (
        <>
            <div className="navbar bg-base-100 shadow-sm">
                <div className="navbar-start">
                <div className="dropdown">
                    <div tabIndex={0} role="button" className="btn btn-ghost lg:hidden">
                    <svg aria-label="Menu" xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"> <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h8m-8 6h16" /> </svg>
                    </div>
                </div>
                <a className="btn btn-ghost text-xl">ITU - Experts Search Engine</a>
                </div>
                <div className="navbar-center hidden lg:flex">
                <ul className="menu menu-horizontal px-1">
                    <li><a>Home</a></li>
                    <li>
                    <details>
                        <summary>Find an expert</summary>
                        <ul className="p-2 bg-base-100 w-40 z-1">
                        <li><a>Search</a></li>
                        <li><a>Chat</a></li>
                        </ul>
                    </details>
                    </li>
                    <li><a>About</a></li>
                </ul>
                </div>
                <div className="navbar-end">
                <a className="btn">Back</a>
                </div>
            </div>
        </>
    )
}

export default Navbar;
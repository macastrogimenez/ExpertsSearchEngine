//import { useState } from 'react'
import './App.css'
import Navbar from './navbar/Navbar'
import { Route, Routes } from 'react-router-dom'
import SearchView from './views/SearchView'
import ExpertDetailView from './views/ExpertDetailView'
import AboutView from './views/AboutView'
import ChatView from './views/ChatView'
import ResultsView from './views/ResultsView'

function App() {
  //const [count, setCount] = useState(0)

  return (
    <>
      <Routes>
        <Route path="/"element={<SearchView></SearchView>}></Route>
        <Route path="/about"element={<AboutView></AboutView>}></Route>
        <Route path='/search' element={<SearchView></SearchView>}></Route>
        <Route path='/chat'element={<ChatView></ChatView>}></Route>
        <Route path='/experts/:id' element={<ExpertDetailView></ExpertDetailView>}></Route>
        <Route path='/results/:query' element={<ResultsView></ResultsView>}></Route>
      </Routes>
      <Navbar></Navbar>

    </>
  )
}

export default App

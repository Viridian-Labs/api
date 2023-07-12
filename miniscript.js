async function prices(){
    const review = [
        "axlATOM",
        "xSHRAP",
        "GMD",
        "CHAM",
        "DEXI",
        "BEAR",
        "BNB",
        "ACS"
    ]
    try{
        const response = await fetch("http://localhost:8000/api/v1/assets")
        const data = await response.json()
        console.log(data)
        const array = []
        for (let token of data["data"]){
            // console.log( data["data"])
            // console.log(token)
            // console.log(`Token: ${token.symbol} Price: ${token.price}`)
            array.push({
                "symbol": token.symbol,
                "price": token.price,
                "stable": token.stable
            })
        }
        array.sort((a, b) => (a.stable < b.stable) ? 1 : -1)
        for (let token of array){
            if(review.includes(token.symbol)){
                console.log(`Token: ${token.symbol} Price: ${token.price}`)
            }
        }
    }
    catch(error){
        console.log(error)
    }
}

prices()
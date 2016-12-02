module Utils exposing (..)

import Html
import Html.Events
import Http
import Json.Decode as JsonDecode
import RemoteData exposing (WebData, RemoteData(..))
import Task


performMsg : a -> Cmd a
performMsg msg =
    Task.perform
        (\x -> msg)
        (\x -> msg)
        (Task.succeed ())


onClick : msg -> Html.Attribute msg
onClick msg =
    Html.Events.onWithOptions
        "click"
        (Html.Events.Options False True)
        (JsonDecode.succeed msg)


andThen :
    (msg -> model -> ( model, Cmd msg ))
    -> msg
    -> ( model, Cmd msg )
    -> ( model, Cmd msg )
andThen update msg ( model, cmd ) =
    let
        ( model_, cmd_ ) =
            update msg model
    in
        ( model_, Cmd.batch [ cmd, cmd_ ] )


onChange : (String -> msg) -> Html.Attribute msg
onChange handler =
    JsonDecode.at [ "target", "value" ] JsonDecode.string
        |> JsonDecode.map handler
        |> Html.Events.on "change"


handleResponse : (String -> a) -> a -> Http.Response -> a
handleResponse handle default response =
    if 200 <= response.status && response.status < 300 then
        case response.value of
            Http.Text text ->
                handle text

            _ ->
                default
    else
        default


decodeResponse : JsonDecode.Decoder a -> a -> Http.Response -> a
decodeResponse decoder default response =
    handleResponse
        (\x -> JsonDecode.decodeString decoder x |> Result.withDefault default)
        default
        response


decodeWebResponse : JsonDecode.Decoder a -> Http.Response -> WebData a
decodeWebResponse decoder response =
    if 200 <= response.status && response.status < 300 then
        case response.value of
            Http.Text str ->
                case JsonDecode.decodeString decoder str of
                    Ok obj ->
                        Success obj

                    Err err ->
                        Failure (Http.UnexpectedPayload err)

            _ ->
                Failure (Http.UnexpectedPayload "Response body is a blob, expecting a string.")
    else
        Failure (Http.BadResponse response.status response.statusText)
